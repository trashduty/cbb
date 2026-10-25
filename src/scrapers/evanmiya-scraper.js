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
    
// Get credentials from GitHub Actions environment variables
const email = process.env.EMAIL;
const password = process.env.PASSWORD;

if (!email || !password) {
  throw new Error('EMAIL or PASSWORD environment variables not configured');
}

// Open the current login dialog
await page.getByRole('button', {
  name: 'Log In',
  exact: true,
}).click({ timeout: config.timeout });

console.log('Opened login dialog');

// Scope the form controls to the login dialog
const loginDialog = page.getByRole('dialog', {
  name: 'Login',
  exact: true,
});

await loginDialog.waitFor({
  state: 'visible',
  timeout: config.timeout,
});

await loginDialog.getByRole('textbox', {
  name: 'Your email',
  exact: true,
}).fill(email);

await loginDialog.getByRole('textbox', {
  name: 'Your password',
  exact: true,
}).fill(password);

await loginDialog.getByRole('button', {
  name: 'Log in',
  exact: true,
}).click();

// Wait for the login dialog to close
await loginDialog.waitFor({
  state: 'hidden',
  timeout: config.timeout,
});

console.log('Login dialog closed');

// Navigate directly to the current predictions page
await page.goto('https://evanmiya.com/game-predictions', {
  waitUntil: 'domcontentloaded',
  timeout: config.timeout,
});

console.log('Navigated to game predictions');

    // Find the current download/export control instead of the old Shiny label.
    const exportControl = page
      .getByRole('button', { name: /download|export/i })
      .or(page.getByRole('link', { name: /download|export/i }))
      .and(page.locator(':visible'));

    try {
      await exportControl.first().waitFor({
        state: 'visible',
        timeout: 30000,
      });
    } catch {
      const controls = await page
        .locator('button:visible, a:visible')
        .evaluateAll(elements =>
          elements.map(element => ({
            role: element.tagName.toLowerCase(),
            label: (
              element.getAttribute('aria-label') ||
              element.textContent ||
              ''
            ).trim().replace(/\s+/g, ' ').slice(0, 120),
          }))
        );

      console.log('Visible page controls:', JSON.stringify(controls, null, 2));
      throw new Error(
        'No visible download/export control was found. ' +
        'Check the error screenshot for the current page or an access message.'
      );
    }

    const controlCount = await exportControl.count();
    if (controlCount !== 1) {
      throw new Error(
        `Found ${controlCount} download/export controls. ` +
        'A more specific selector is required; check the error screenshot.'
      );
    }

    console.log('Found download/export control');

    // Handle rejection immediately, including when the click itself fails.
    const downloadResultPromise = page
      .waitForEvent('download', { timeout: 60000 })
      .then(
        download => ({ download }),
        error => ({ error })
      );

    await exportControl.click({ timeout: 15000 });
    console.log('Clicked download/export control');

    const downloadResult = await downloadResultPromise;
    if (downloadResult.error) {
      throw new Error(
        'The download/export control was clicked, but no browser download ' +
        'started within 60 seconds. It may open an export menu instead.'
      );
    }

    const download = downloadResult.download;

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
