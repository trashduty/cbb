/**
 * EvanMiya Scraper
 * 
 * This script logs into the EvanMiya website and downloads the latest basketball data.
 * It outputs a CSV file to data/em.csv
 */

const { chromium } = require('@playwright/test');
require('dotenv').config();
const path = require('path');
const fs = require('fs');
const csv = require('csv-parser');

// Configuration for the scraper
const config = {
  url: 'https://evanmiya.com/',
  outputFile: path.join(__dirname, '../../data/em.csv'),
  maxRetries: 3,
  retryDelay: 2000, // ms
  timeout: 30000, // ms
};

/**
 * Creates directory if it doesn't exist
 * @param {string} dirPath - Path to directory
 */
function ensureDirectoryExists(dirPath) {
  if (!fs.existsSync(dirPath)) {
    fs.mkdirSync(dirPath, { recursive: true });
    console.log(`Created directory: ${dirPath}`);
  }
}

/**
 * Sleep function for delays
 * @param {number} ms - Milliseconds to sleep
 * @returns {Promise<void>}
 */
async function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

/**
 * Process the downloaded CSV file to fix spread directions
 * @param {string} filePath - Path to the downloaded CSV
 * @returns {Promise<void>}
 */
async function processSpreadDirections(filePath) {
  return new Promise((resolve, reject) => {
    if (!fs.existsSync(filePath)) {
      return reject(new Error(`File not found: ${filePath}`));
    }

    const results = [];
    fs.createReadStream(filePath)
      .pipe(csv())
      .on('data', (data) => results.push(data))
      .on('end', () => {
        if (results.length === 0) {
          console.log('No data found in CSV file');
          return resolve();
        }
        
        // Log all column names first to help identify which ones need correction
        const allColumns = Object.keys(results[0]);
        console.log('All columns in CSV:', allColumns.join(', '));
        
        // Specifically target the line column as requested (EvanMiya's predicted spread)
        const columnsToInvert = ['line'];
        
        // Check if the column exists in the data
        if (!allColumns.includes('line')) {
          console.log('Warning: line column not found in the CSV. Available columns:');
          console.log(allColumns.join(', '));
          
          // Log potential spread-related columns for reference
          const potentialSpreadColumns = allColumns.filter(col => 
            col.toLowerCase().includes('spread') || 
            col.toLowerCase().includes('line') || 
            col.toLowerCase().includes('handicap')
          );
          
          if (potentialSpreadColumns.length > 0) {
            console.log('Potential spread-related columns found:');
            potentialSpreadColumns.forEach(col => console.log(`- ${col}`));
          }
          
          return resolve();
        }
        
        console.log(`Will invert the line column values`);
        
        // Fix spread directions by inverting the values for the line column
        let updatedCount = 0;
        results.forEach(row => {
          if (row.line && !isNaN(parseFloat(row.line))) {
            // Invert the spread value to fix direction
            row.line = (-1 * parseFloat(row.line)).toString();
            updatedCount++;
          }
        });

        // Write back to CSV
        const headers = Object.keys(results[0]);
        const csvContent = [
          headers.join(','),
          ...results.map(row => headers.map(header => row[header]).join(','))
        ].join('\n');

        fs.writeFileSync(filePath, csvContent);
        console.log(`Fixed spread directions in ${filePath} for line column. Updated ${updatedCount} values.`);
        
        resolve();
      })
      .on('error', reject);
  });
}

/**
 * Main function to download data from EvanMiya
 * @returns {Promise<Object>} - Result object with success status
 */
async function downloadEvanMiyaData() {
  // Create data directory if it doesn't exist
  const dataDir = path.dirname(config.outputFile);
  ensureDirectoryExists(dataDir);
  
  // Launch browser
  const browser = await chromium.launch();
  const context = await browser.newContext({
    acceptDownloads: true,
    recordVideo: process.env.RECORD_VIDEO === 'true' ? {
      dir: path.join(dataDir, 'videos'),
    } : undefined,
  });

  try {
    console.log('Starting EvanMiya data download process...');
    const page = await context.newPage();
    
    // Go to site with timeout
    await page.goto(config.url, { timeout: config.timeout });
    console.log('Loaded EvanMiya website');
    
    // Accept cookies if prompted
    try {
      await page.getByRole('button', { name: 'OK' }).click({ timeout: 10000 });
      console.log('Accepted cookies');
    } catch (e) {
      console.log('No cookie banner found or already accepted');
    }
    
    // Login to the site
    await page.getByRole('button', { name: 'Login' }).click();
    console.log('Clicked login button');
    
    // Get credentials from environment variables
    const email = process.env.EMAIL;
    const password = process.env.PASSWORD;
    
    if (!email || !password) {
      throw new Error('EMAIL or PASSWORD environment variables not configured');
    }
    
    // Fill login form
    await page.getByRole('textbox', { name: 'Your email' }).fill(email);
    await page.getByRole('textbox', { name: 'Your password' }).fill(password);
    await page.getByRole('button', { name: 'Log in' }).click();
    
    // Wait for login to complete
    await page.waitForLoadState('networkidle', { timeout: config.timeout });
    console.log('Login completed');
    
    // Navigate to Game > Upcoming
    await page.getByRole('link', { name: 'chart-line icon Game' }).click();
    console.log('Navigated to Game section');
    
    await page.getByRole('link', { name: 'angles-right icon Upcoming' }).click();
    console.log('Navigated to Upcoming games');
    
    // Wait for page to load
    await page.waitForLoadState('networkidle', { timeout: config.timeout });
    
    // Navigate to game predictions page
    await page.goto('https://evanmiya.com/?game_predictions', { timeout: config.timeout });
    console.log('Navigated to game predictions');
    
    // Setup download handler and click download button
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('button', { name: 'download icon Download' }).click();
    console.log('Clicked download button');
    
    const download = await downloadPromise;
    
    // Save the file to the specified output path
    await download.saveAs(config.outputFile);
    console.log(`File downloaded successfully to: ${config.outputFile}`);
    
    // Process the CSV to fix spread directions
    await processSpreadDirections(config.outputFile);
    
    return {
      success: true,
      filePath: config.outputFile,
      timestamp: new Date().toISOString(),
    };
  } catch (error) {
    console.error('Error occurred during download process:', error);
    
    // Take screenshot of error state
    try {
      const page = await context.pages()[0];
      if (page) {
        const screenshotPath = path.join(dataDir, `error_${new Date().toISOString().replace(/:/g, '-')}.png`);
        await page.screenshot({ path: screenshotPath });
        console.log(`Error screenshot saved to: ${screenshotPath}`);
      }
    } catch (e) {
      console.error('Failed to capture error screenshot:', e);
    }
    
    return {
      success: false,
      error: error.message,
      timestamp: new Date().toISOString(),
    };
  } finally {
    // Clean up resources
    await context.close();
    await browser.close();
    console.log('Browser closed');
  }
}

/**
 * Run the EvanMiya scraper with retry logic
 * @returns {Promise<Object>} - Result of the scraping operation
 */
async function runWithRetry() {
  let retries = 0;
  let result;
  
  while (retries <= config.maxRetries) {
    if (retries > 0) {
      console.log(`Retry attempt ${retries}/${config.maxRetries}...`);
      await sleep(config.retryDelay);
    }
    
    result = await downloadEvanMiyaData();
    
    if (result.success) {
      break;
    }
    
    retries++;
  }
  
  if (!result.success) {
    console.error(`Failed after ${config.maxRetries} retry attempts`);
  }
  
  return result;
}

// If running this script directly, execute the scraper
if (require.main === module) {
  runWithRetry().then(result => {
    if (result.success) {
      console.log('Download completed successfully');
      process.exit(0);
    } else {
      console.error('Download failed:', result.error);
      process.exit(1);
    }
  });
}

module.exports = { runWithRetry }; 