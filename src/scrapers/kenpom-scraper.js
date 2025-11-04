/**
 * KenPom Scraper
 * 
 * This script logs into the KenPom website and downloads FanMatch HTML data.
 * It then calls the Python parser to convert the HTML to CSV format.
 * The CSV file is saved to data/kp.csv
 */

const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Load environment variables FIRST before using them in CONFIG
require('dotenv').config();

// Configuration options
const CONFIG = {
  waitForNewDays: false, // Set to true if you want to wait for new days to appear
  maxChecks: 10, // Maximum number of checks for new days
  waitTimeBetweenChecks: 60000, // Wait time in ms between checks (1 minute)
  saveHTML: true, // Save HTML of each page
  outputDir: path.join(__dirname, '../../kenpom-data'), // Directory to save HTML and data
  csvOutputPath: path.join(__dirname, '../../data/kp.csv'), // Fixed output path for the CSV
  headless: true, // Run in headless mode (no browser UI)
  navigationTimeout: 60000, // Navigation timeout in ms (60 seconds)
  // Load credentials from environment variables
  credentials: {
    email: process.env.EMAIL || '',
    password: process.env.PASSWORD || ''
  },
  // User agent to mimic a real browser
  userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
};

/**
 * Ensures a directory exists, creating it if necessary
 * @param {string} directory - Path to directory
 */
function ensureDirectoryExists(directory) {
  if (!fs.existsSync(directory)) {
    fs.mkdirSync(directory, { recursive: true });
    console.log(`Created directory: ${directory}`);
  }
}

/**
 * Saves HTML content to a file
 * @param {Object} page - Playwright Page object
 * @param {string} filename - Filename to save HTML as
 * @returns {Promise<string|undefined>} - Path to saved file or undefined if saving is disabled
 */
async function saveHTMLToFile(page, filename) {
  if (!CONFIG.saveHTML) return;
  
  try {
    ensureDirectoryExists(CONFIG.outputDir);
    const content = await page.content();
    const filePath = path.join(CONFIG.outputDir, filename);
    fs.writeFileSync(filePath, content);
    console.log(`Saved HTML to ${filePath}`);
    return filePath;
  } catch (error) {
    console.error(`Error saving HTML to file: ${error.message}`);
  }
}

/**
 * Runs the Python parser to convert HTML files to CSV
 * @returns {boolean} - Success status
 */
function runParser() {
  try {
    console.log('Running KenPom parser to generate CSV file...');
    
    // Ensure the data directory exists
    const dataDir = path.dirname(CONFIG.csvOutputPath);
    ensureDirectoryExists(dataDir);
    
    // Determine the path to the parser script relative to this file
    const parserPath = path.join(__dirname, '../parsers/kenpom-parser.py');
    
    // Run the Python parser script using UV run
    const command = `uv run ${parserPath} --html-dir "${CONFIG.outputDir}" --output "${CONFIG.csvOutputPath}"`;
    console.log(`Executing command: ${command}`);
    
    // Execute the command
    const output = execSync(command, { encoding: 'utf8' });
    console.log('Parser output:', output);
    
    console.log(`CSV data has been generated at: ${CONFIG.csvOutputPath}`);
    return true;
  } catch (error) {
    console.error('Error running parser:', error.message);
    return false;
  }
}

/**
 * Main scraper function
 */
async function runScraper() {
  // Ensure output directory exists
  ensureDirectoryExists(CONFIG.outputDir);

  // Launch browser with more realistic settings to bypass Cloudflare
  const browser = await chromium.launch({
    headless: CONFIG.headless,
    args: [
      '--disable-blink-features=AutomationControlled',
      '--no-sandbox',
      '--disable-web-security'
    ]
  });
  
  console.log('Browser launched');
  
  // Create a new context with more human-like behavior
  const context = await browser.newContext({
    userAgent: CONFIG.userAgent,
    viewport: { width: 1920, height: 1080 },
    screen: { width: 1920, height: 1080 },
    deviceScaleFactor: 1,
    ignoreHTTPSErrors: true,
    javaScriptEnabled: true
  });
  
  try {
    console.log('Starting to scrape FanMatch data...');
    
    // Create a page
    const page = await context.newPage();
    
    // Define cookies path
    const cookiesPath = path.join(CONFIG.outputDir, 'cookies.json');
    
    /**
     * Handles the login process
     * @returns {Promise<boolean>} - True if login was successful
     */
    const handleLogin = async () => {
      console.log('Login required. Proceeding with login...');
      
      // Go to the login page
      await page.goto('https://kenpom.com/register-kenpom.php?frompage=1', { 
        waitUntil: 'domcontentloaded',
        timeout: CONFIG.navigationTimeout 
      });
      
      // Handle login with retry logic
      let loginAttempts = 0;
      const maxLoginAttempts = 3;
      
      while (loginAttempts < maxLoginAttempts) {
        try {
          console.log(`Login attempt ${loginAttempts + 1}/${maxLoginAttempts}`);

          // Verify we have credentials
          if (!CONFIG.credentials.email || !CONFIG.credentials.password) {
            throw new Error('Email or password not set in environment variables');
          }

          console.log(`Using email: ${CONFIG.credentials.email.substring(0, 3)}...`);

          // Wait for the form to be ready
          console.log('Waiting for email input field...');
          await page.waitForSelector('input[name="email"]', { state: 'visible', timeout: 10000 });

          console.log('Waiting for password input field...');
          await page.waitForSelector('input[name="password"]', { state: 'visible', timeout: 10000 });

          console.log('Waiting for submit button...');
          await page.waitForSelector('input[type="submit"]', { state: 'visible', timeout: 10000 });

          // Fill in the credentials
          console.log('Filling email field...');
          await page.fill('input[name="email"]', CONFIG.credentials.email);

          console.log('Filling password field...');
          await page.fill('input[name="password"]', CONFIG.credentials.password);

          // Add a small delay before clicking submit
          await new Promise(resolve => setTimeout(resolve, 500));

          console.log('Clicking submit button...');
          await page.click('input[type="submit"]');

          // Wait for navigation to complete
          console.log('Waiting for navigation after login...');
          try {
            await page.waitForURL(url => !url.includes('register-kenpom.php'), {
              timeout: 30000
            });
          } catch (e) {
            console.log(`Navigation wait timed out: ${e.message}`);
          }

          // Wait a moment for any redirects to complete
          await new Promise(resolve => setTimeout(resolve, 2000));

          // Check current URL
          const currentUrl = page.url();
          console.log(`Current URL after login attempt: ${currentUrl}`);

          // Check if login was successful
          const isLoggedIn = !currentUrl.includes('register-kenpom.php');

          if (isLoggedIn) {
            console.log('✓ Logged in successfully');

            // Save cookies for future use
            const cookies = await context.cookies();
            fs.writeFileSync(cookiesPath, JSON.stringify(cookies, null, 2));
            console.log('Saved cookies to file');

            // Navigate to FanMatch with more reliable DOM loading
            await navigateToFanMatch(page);

            return true; // Login successful
          } else {
            console.log('✗ Login unsuccessful - still on login page');
            loginAttempts++;

            // Take a screenshot for debugging
            const screenshotPath = path.join(CONFIG.outputDir, `login-fail-${loginAttempts}.png`);
            await page.screenshot({ path: screenshotPath });
            console.log(`Screenshot saved to ${screenshotPath}`);

            if (loginAttempts < maxLoginAttempts) {
              console.log('Waiting before retry...');
              await new Promise(resolve => setTimeout(resolve, 3000));
            }
          }
        } catch (loginError) {
          console.error(`Login attempt ${loginAttempts + 1} failed:`, loginError.message);
          loginAttempts++;
          
          if (loginAttempts >= maxLoginAttempts) {
            throw new Error(`Failed to login after ${maxLoginAttempts} attempts`);
          }
          
          await new Promise(resolve => setTimeout(resolve, 3000));
        }
      }
      
      return false; // Login failed
    };
    
    /**
     * Navigates to the FanMatch page
     * @param {Object} page - Playwright Page object
     * @returns {Promise<boolean>} - True if navigation was successful
     */
    const navigateToFanMatch = async (page) => {
      console.log('Navigating to FanMatch page...');
      
      // Use more reliable loading condition
      try {
        await page.goto('https://kenpom.com/fanmatch.php', {
          waitUntil: 'domcontentloaded', // More reliable than networkidle
          timeout: CONFIG.navigationTimeout
        });
        
        // Add a manual timeout to ensure page is fully loaded
        await new Promise(resolve => setTimeout(resolve, 3000));
        
        // Check if navigation was successful
        const pageTitle = await page.title();
        if (pageTitle && pageTitle.includes('KenPom.com')) {
          console.log('Successfully loaded FanMatch page');
          return true;
        } else {
          console.log('Page loaded but may not be FanMatch, checking content...');
          // Check if the page has the fanmatch table
          const hasFanMatchTable = await page.evaluate(() => {
            return !!document.querySelector('#fanmatch-table');
          });
          
          if (hasFanMatchTable) {
            console.log('FanMatch table found');
            return true;
          } else {
            console.log('FanMatch table not found');
            return false;
          }
        }
      } catch (error) {
        console.error('Error navigating to FanMatch:', error.message);
        return false;
      }
    };
    
    // Try to access FanMatch page
    let accessSuccessful = false;
    
    // First try direct navigation
    accessSuccessful = await navigateToFanMatch(page);
    
    // If direct navigation fails, try login
    if (!accessSuccessful) {
      const loginSuccessful = await handleLogin();
      if (loginSuccessful) {
        accessSuccessful = true;
      } else {
        accessSuccessful = false;
      }
    }

    if (!accessSuccessful) {
      throw new Error('Could not access FanMatch page after multiple attempts');
    }
    
    console.log('Successfully accessed FanMatch');
    
    // Save initial FanMatch page HTML
    await saveHTMLToFile(page, 'fanmatch-initial.html');
    
    // Set to track visited dates to avoid loops
    let visitedDates = new Set();
    let canContinue = true;
    let reachedLatestDay = false;
    let checkCount = 0;

    // Track starting date to limit scraping to 10 days in advance
    const startDate = new Date();
    const maxDaysInAdvance = 10;

    // Process to keep going forward through days
    while (canContinue) {
      // Get the current URL
      const currentUrl = await page.url();
      console.log(`Currently at: ${currentUrl}`);
      
      // Extract current date information from the page
      const currentDateInfo = await page.evaluate(() => {
        // Look for the date information div
        const dateDiv = document.querySelector('div.lh12');
        if (dateDiv) {
          // First try: extract from the archive link (most reliable as it has the full date with year)
          const archiveLink = dateDiv.querySelector('a[href^="archive.php?d="]');
          if (archiveLink) {
            const href = archiveLink.getAttribute('href');
            const match = href.match(/d=(\d{4})-(\d{2})-(\d{2})/);
            if (match) {
              return {
                year: parseInt(match[1], 10),
                month: parseInt(match[2], 10),
                day: parseInt(match[3], 10),
                dateString: `${match[1]}-${match[2]}-${match[3]}`,
                text: `${match[1]}-${match[2]}-${match[3]}`
              };
            }
          }
          
          // Second try: Extract from text like "for Wednesday, March 12th"
          const dateText = dateDiv.textContent;
          const dayMatch = dateText.match(/for\s+\w+,\s+(\w+)\s+(\d+)/i);
          if (dayMatch) {
            const month = dayMatch[1]; // e.g., "March"
            const day = parseInt(dayMatch[2], 10); // e.g., 11
            
            // Convert month name to number
            const monthMap = {
              'january': 1, 'february': 2, 'march': 3, 'april': 4, 'may': 5, 'june': 6,
              'july': 7, 'august': 8, 'september': 9, 'october': 10, 'november': 11, 'december': 12
            };
            
            const monthNum = monthMap[month.toLowerCase()];
            
            // Get year from URL if possible
            const urlMatch = window.location.href.match(/d=(\d{4})-/);
            const year = urlMatch ? parseInt(urlMatch[1], 10) : new Date().getFullYear();
            
            return {
              year: year,
              month: monthNum,
              day: day,
              dateString: `${year}-${String(monthNum).padStart(2, '0')}-${String(day).padStart(2, '0')}`,
              text: `${month} ${day}, ${year}`
            };
          }
        }
        
        // If we reach here, we couldn't extract the date
        console.log("Warning: Could not extract date from page");
        const now = new Date();
        return {
          year: now.getFullYear(),
          month: now.getMonth() + 1,
          day: now.getDate(),
          dateString: now.toISOString().split('T')[0],
          text: "Current date (fallback)"
        };
      });
      
      if (currentDateInfo) {
        console.log(`Extracted current date from page: ${currentDateInfo.text}`);
        
        // Use the formatted dateString directly
        if (currentDateInfo.dateString) {
          await saveHTMLToFile(page, `fanmatch-${currentDateInfo.dateString}.html`);
        } else {
          // Fallback to manual formatting
          const year = currentDateInfo.year || new Date().getFullYear();
          const month = currentDateInfo.month.toString().padStart(2, '0');
          const day = currentDateInfo.day.toString().padStart(2, '0');
          
          await saveHTMLToFile(page, `fanmatch-${year}-${month}-${day}.html`);
        }
      } else {
        console.log('Could not extract current date from page, using URL or timestamp');
        
        // Try to extract date from URL or use timestamp
        let dateStr = 'unknown-date';
        const dateMatch = currentUrl.match(/d=(\d{4}-\d{2}-\d{2})/);
        if (dateMatch) {
          dateStr = dateMatch[1];
        } else {
          dateStr = new Date().toISOString().split('T')[0];
        }
        
        await saveHTMLToFile(page, `fanmatch-${dateStr}.html`);
      }
      
      // Find day links in the MM/DD format that link to fanmatch.php
      const dayLinks = await page.evaluate(() => {
        // Get all links on the page
        const links = Array.from(document.querySelectorAll('a'));
        
        // Filter for day links with MM/DD format that point to fanmatch.php
        return links
          .filter(link => {
            const text = link.textContent.trim();
            const href = link.getAttribute('href') || '';
            
            // Match MM/DD format (like 03/12)
            const isDayFormat = /^\d{2}\/\d{2}$/.test(text);
            
            // Ensure it links to fanmatch.php
            const isFanMatchLink = href.includes('fanmatch.php');
            
            return isDayFormat && isFanMatchLink;
          })
          .map(link => {
            const text = link.textContent.trim();
            const href = link.getAttribute('href') || '';
            
            // Extract the full date from the URL (preferred method)
            let fullDate = null;
            let year, month, day;
            
            if (href.includes('d=')) {
              const match = href.match(/d=(\d{4})-(\d{2})-(\d{2})/);
              if (match) {
                year = parseInt(match[1], 10);
                month = parseInt(match[2], 10);
                day = parseInt(match[3], 10);
                fullDate = `${match[1]}-${match[2]}-${match[3]}`;
              }
            }
            
            // Fallback: Parse the date from the link text (MM/DD)
            if (!month || !day) {
              const parts = text.split('/').map(part => parseInt(part, 10));
              month = parts[0] || null;
              day = parts[1] || null;
              
              // If we have month/day from text but no year from URL, use current year
              if (month && day && !year) {
                year = new Date().getFullYear();
                // Format the full date with the current year
                const monthStr = month.toString().padStart(2, '0');
                const dayStr = day.toString().padStart(2, '0');
                fullDate = `${year}-${monthStr}-${dayStr}`;
              }
            }
            
            return {
              text,
              href,
              year,
              month,
              day,
              fullDate
            };
          });
      });
      
      console.log(`Found ${dayLinks.length} day links on the current page`);

      if (dayLinks.length > 0) {
        // Log all day links found
        dayLinks.forEach(link => {
          console.log(`- Date: "${link.text}", Href: "${link.href}"`);
        });
        
        // Get the current date to use as reference
        let currentMonth, currentDay;
        
        // First try using the date extracted from the page
        if (currentDateInfo && currentDateInfo.month && currentDateInfo.day) {
          currentMonth = currentDateInfo.month;
          currentDay = currentDateInfo.day;
        } else {
          // Fallback: Try to extract from URL
          let currentDateMatch = currentUrl.match(/d=(\d{4})-(\d{2})-(\d{2})/);
          if (currentDateMatch) {
            currentMonth = parseInt(currentDateMatch[2], 10);
            currentDay = parseInt(currentDateMatch[3], 10);
          } else {
            // Last resort: use system date
            const now = new Date();
            currentMonth = now.getMonth() + 1; // JS months are 0-indexed
            currentDay = now.getDate();
          }
        }
        
        console.log(`Current date reference: Month: ${currentMonth}, Day: ${currentDay}`);
        
        // Find the next day link (the one with the closest future date)
        const forwardLinks = dayLinks.filter(link => {
          // Convert date to a string key for tracking visited dates
          const dateKey = `${link.month}-${link.day}`;

          // Skip if we've already visited this date
          if (visitedDates.has(dateKey)) {
            return false;
          }

          // Check if this date is within maxDaysInAdvance from start
          if (link.year && link.month && link.day) {
            const linkDate = new Date(link.year, link.month - 1, link.day);
            const daysDiff = Math.floor((linkDate - startDate) / (1000 * 60 * 60 * 24));

            if (daysDiff > maxDaysInAdvance) {
              console.log(`Skipping date ${link.text} - exceeds ${maxDaysInAdvance} day limit (${daysDiff} days from start)`);
              return false;
            }
          }

          // Check if this date is in the future relative to our current position
          if (link.month > currentMonth) {
            return true;
          } else if (link.month === currentMonth) {
            return link.day > currentDay;
          }

          return false;
        });
        
        if (forwardLinks.length > 0) {
          // Reset the check counter since we found a new forward link
          reachedLatestDay = false;
          checkCount = 0;
          
          // Sort by month and day to find the closest next date
          forwardLinks.sort((a, b) => {
            if (a.month !== b.month) {
              return a.month - b.month;
            }
            return a.day - b.day;
          });
          
          // Select the first link (closest future date)
          const nextLink = forwardLinks[0];
          const dateKey = `${nextLink.month}-${nextLink.day}`;
          console.log(`Moving to date ${nextLink.text} (${nextLink.href})`);
          
          // Mark this date as visited
          visitedDates.add(dateKey);
          
          // Navigate to the link
          try {
            console.log(`Clicking on date link: ${nextLink.text}`);
            
            // Try to click the link
            const linkElement = await page.$(`a:text("${nextLink.text}")`);
            
            if (linkElement) {
              await linkElement.click();
              console.log(`Successfully clicked on date link: ${nextLink.text}`);
            } else {
              throw new Error(`Could not find link element with text: ${nextLink.text}`);
            }
          } catch (error) {
            console.log(`Could not click date link. Trying direct navigation...`);
            
            // Fallback to navigating directly to the URL
            const fullUrl = nextLink.href.startsWith('http') 
              ? nextLink.href 
              : new URL(nextLink.href, 'https://kenpom.com').toString();
              
            console.log(`Navigating to: ${fullUrl}`);
            await page.goto(fullUrl, { 
              waitUntil: 'networkidle',
              timeout: CONFIG.navigationTimeout 
            });
          }
          
          // Wait for navigation to complete
          await page.waitForLoadState('networkidle', { timeout: CONFIG.navigationTimeout })
            .catch(e => console.log(`Navigation timeout: ${e.message}`));
          
          // Brief delay between pages
          await new Promise(resolve => setTimeout(resolve, 1000));
        } else {
          // No more forward links found
          if (CONFIG.waitForNewDays) {
            if (!reachedLatestDay) {
              console.log('Reached the most recent day. Will check periodically for new days.');
              reachedLatestDay = true;
            }
            
            checkCount++;
            
            if (checkCount <= CONFIG.maxChecks) {
              console.log(`Check ${checkCount}/${CONFIG.maxChecks}: Waiting for new day links...`);
              await new Promise(resolve => setTimeout(resolve, CONFIG.waitTimeBetweenChecks));
              
              console.log('Refreshing page to check for new day links...');
              await page.reload({ waitUntil: 'networkidle' });
              
              // Save HTML after refresh
              await saveHTMLToFile(page, `fanmatch-refresh-${checkCount}.html`);
            } else {
              console.log(`Reached maximum number of checks. No new days found.`);
              canContinue = false;
            }
          } else {
            console.log('No more forward day links available. Stopping navigation.');
            canContinue = false;
          }
        }
      } else {
        console.log('No day links found on this page. Stopping navigation.');
        canContinue = false;
      }
    }
    
    console.log('All future day links have been processed');
    
    // Create a summary file with links to all downloaded pages
    if (CONFIG.saveHTML) {
      try {
        const files = fs.readdirSync(CONFIG.outputDir).filter(file => file.endsWith('.html'));
        const summary = files.map(file => {
          return `- ${file}`;
        }).join('\n');
        
        fs.writeFileSync(path.join(CONFIG.outputDir, 'summary.txt'), 
          `Downloaded ${files.length} HTML files:\n${summary}`);
        console.log(`Created summary file with ${files.length} HTML files`);
      } catch (error) {
        console.error('Error creating summary file:', error);
      }
    }
    
    console.log('All scraping actions completed successfully');
    
    // Run the Python parser to generate the CSV file
    runParser();
    
  } catch (error) {
    console.error('Error during scraping:', error);
    console.error(error.stack);
  } finally {
    // Close browser
    await browser.close();
    console.log('Browser closed');
  }
}

// If running this script directly, execute the scraper
if (require.main === module) {
  // Load environment variables
  require('dotenv').config();
  
  // Run the scraper
  runScraper().catch(error => {
    console.error('Scraper failed:', error);
    process.exit(1);
  });
}

module.exports = { runScraper };