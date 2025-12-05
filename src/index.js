/**
 * Main entry point for KP-EM-Scrape
 * This script orchestrates running all scrapers in sequence
 */

const { spawn } = require('child_process');
const path = require('path');
const fs = require('fs');
const csv = require('csv-parser');
const { createObjectCsvWriter } = require('csv-writer');

// Load environment variables
require('dotenv').config();

// Import the EvanMiya transformer
const { transformEvanMiyaData } = require('./transformers/evanmiya-transformer');

// Directory where scrapers will output data
const dataDir = path.join(__dirname, '..', 'data');

// Ensure the data directory exists
if (!fs.existsSync(dataDir)) {
  fs.mkdirSync(dataDir, { recursive: true });
  console.log(`Created directory: ${dataDir}`);
}

/**
 * Run a script and return a promise that resolves when it completes
 * @param {string} scriptPath - Path to the script file
 * @param {string} scriptName - Name of the script for logging
 * @returns {Promise<void>} - Promise that resolves when script completes
 */
function runScript(scriptPath, scriptName) {
  return new Promise((resolve, reject) => {
    console.log(`Starting ${scriptName} scraper...`);

    const childProcess = spawn('node', [scriptPath], {
      stdio: 'inherit',
      shell: true,
      env: process.env
    });

    childProcess.on('close', (code) => {
      if (code === 0) {
        console.log(`${scriptName} scraper completed successfully`);
        resolve();
      } else {
        console.error(`${scriptName} scraper failed with code ${code}`);
        reject(new Error(`${scriptName} scraper failed with code ${code}`));
      }
    });

    childProcess.on('error', (err) => {
      console.error(`Error running ${scriptName} scraper:`, err);
      reject(err);
    });
  });
}

/**
 * Run a UV script and return a promise that resolves when it completes
 * @param {string} scriptPath - Path to the UV script
 * @param {string} scriptName - Name of the script for logging
 * @returns {Promise<void>} - Promise that resolves when script completes
 */
function runUVScript(scriptPath, scriptName) {
  return new Promise((resolve, reject) => {
    console.log(`Starting ${scriptName} UV script...`);

    const childProcess = spawn('uv', ['run', scriptPath], {
      stdio: 'inherit',
      shell: true,
      env: process.env
    });

    childProcess.on('close', (code) => {
      if (code === 0) {
        console.log(`${scriptName} script completed successfully`);
        resolve();
      } else {
        console.error(`${scriptName} script failed with code ${code}`);
        reject(new Error(`${scriptName} script failed with code ${code}`));
      }
    });

    childProcess.on('error', (err) => {
      console.error(`Error running ${scriptName} script:`, err);
      reject(err);
    });
  });
}

/**
 * Read a CSV file and return its contents as an array of objects
 * @param {string} filePath - Path to the CSV file
 * @returns {Promise<Array>} - Promise that resolves to an array of objects
 */
function readCsvFile(filePath) {
  return new Promise((resolve, reject) => {
    const results = [];
    
    fs.createReadStream(filePath)
      .pipe(csv())
      .on('data', (data) => results.push(data))
      .on('end', () => {
        console.log(`Read ${results.length} records from ${path.basename(filePath)}`);
        resolve(results);
      })
      .on('error', (err) => {
        reject(err);
      });
  });
}

/**
 * Join the datasets (KenPom, EvanMiya, Barttorvik, and Hasla)
 * Performs an inner join between KenPom and EvanMiya, then left joins with Barttorvik and Hasla
 * @returns {Promise<void>} - Promise that resolves when join is complete
 */
async function joinDatasets() {
  console.log("Joining KenPom, EvanMiya, Barttorvik, and Hasla datasets...");
  
  try {
    // Read the CSV files
    const kpData = await readCsvFile(path.join(dataDir, 'kp_mapped.csv'));
    const emData = await readCsvFile(path.join(dataDir, 'em_mapped.csv'));
    
    // Read Barttorvik data
    const btMappedFile = path.join(dataDir, 'bt_mapped.csv');
    let btData = [];
    
    if (fs.existsSync(btMappedFile)) {
      btData = await readCsvFile(btMappedFile);
    } else {
      console.warn("Barttorvik data file not found, proceeding with empty Barttorvik dataset");
    }
    
    // Read Hasla data
    const haslaMappedFile = path.join(dataDir, 'hasla_mapped.csv');
    let haslaData = [];
    
    if (fs.existsSync(haslaMappedFile)) {
      haslaData = await readCsvFile(haslaMappedFile);
    } else {
      console.warn("Hasla data file not found, proceeding with empty Hasla dataset");
    }
    
    // Create lookup objects for faster joins
    // Use Map instead of plain objects for better performance with larger datasets

    // Create KenPom lookup with both orderings
    const kpLookup = new Map();
    const kpSwappedLookup = new Map();
    kpData.forEach(item => {
      // Original ordering
      const key = `${item['Team']}_${item['Home Team']}_${item['Away Team']}`;
      kpLookup.set(key, item);

      // Swapped ordering
      const swappedKey = `${item['Team']}_${item['Away Team']}_${item['Home Team']}`;
      const swappedItem = {
        ...item,
        'Home Team': item['Away Team'],
        'Away Team': item['Home Team'],
        'spread_kenpom': item['spread_kenpom'] ? -item['spread_kenpom'] : null,
        'win_prob_kenpom': item['win_prob_kenpom'] ? 1 - item['win_prob_kenpom'] : null
      };
      kpSwappedLookup.set(swappedKey, swappedItem);
    });

    // Create Barttorvik lookup with both orderings
    const btLookup = new Map();
    const btSwappedLookup = new Map();
    btData.forEach(item => {
      // Original ordering
      const key = `${item['Team']}_${item['Home Team']}_${item['Away Team']}`;
      btLookup.set(key, item);
      
      // Swapped ordering
      const swappedKey = `${item['Team']}_${item['Away Team']}_${item['Home Team']}`;
      const swappedItem = {
        ...item,
        'Home Team': item['Away Team'],
        'Away Team': item['Home Team'],
        'spread_barttorvik': item['spread_barttorvik'] ? -item['spread_barttorvik'] : null,
        'win_prob_barttorvik': item['win_prob_barttorvik'] ? 1 - item['win_prob_barttorvik'] : null
      };
      btSwappedLookup.set(swappedKey, swappedItem);
    });
    
    // Create Hasla lookup with both orderings
    const haslaLookup = new Map();
    const haslaSwappedLookup = new Map();
    haslaData.forEach(item => {
      // Original ordering
      const key = `${item['Team']}_${item['Home Team']}_${item['Away Team']}`;
      haslaLookup.set(key, item);
      
      // Swapped ordering
      const swappedKey = `${item['Team']}_${item['Away Team']}_${item['Home Team']}`;
      const swappedItem = {
        ...item,
        'Home Team': item['Away Team'],
        'Away Team': item['Home Team'],
        'spread_hasla': item['spread_hasla'] ? -item['spread_hasla'] : null,
        'win_prob_hasla': item['win_prob_hasla'] ? 1 - item['win_prob_hasla'] : null
      };
      haslaSwappedLookup.set(swappedKey, swappedItem);
    });
    
    // First perform left join between EvanMiya and KenPom (iterate over EvanMiya to keep all EM games)
    const leftJoinResult = [];

    // Get all possible KP columns by looking at first record (or any record)
    const kpColumns = kpData.length > 0 ?
      Object.keys(kpData[0]).filter(key => !['Team', 'Home Team', 'Away Team', 'Game Date'].includes(key)) :
      [];

    for (const emItem of emData) {
      const compositeKey = `${emItem['Team']}_${emItem['Home Team']}_${emItem['Away Team']}`;
      const swappedKey = `${emItem['Team']}_${emItem['Away Team']}_${emItem['Home Team']}`;

      // Try both orderings
      const kpItem = kpLookup.get(compositeKey) || kpSwappedLookup.get(swappedKey);

      // Start with EM data
      const combinedItem = { ...emItem };

      // Initialize all KP columns as null
      kpColumns.forEach(col => {
        combinedItem[col] = null;
      });

      // Add KP data if it exists
      if (kpItem) {
        kpColumns.forEach(col => {
          combinedItem[col] = kpItem[col];
        });
      }

      leftJoinResult.push(combinedItem);
    }

    console.log(`Left join produced ${leftJoinResult.length} records`);
    
    // Now perform left join with Barttorvik data
    const afterBtResult = [];
    let barttorvikMatches = 0;
    
    for (const item of leftJoinResult) {
      const fullBtKey = `${item['Team']}_${item['Home Team']}_${item['Away Team']}`;
      const swappedBtKey = `${item['Team']}_${item['Away Team']}_${item['Home Team']}`;
      
      // Try both orderings
      const btItem = btLookup.get(fullBtKey) || btSwappedLookup.get(swappedBtKey);
      
      // Always include original item and initialize Barttorvik fields as null
      const newItem = {
        ...item,
        spread_barttorvik: null,
        win_prob_barttorvik: null,
        projected_total_barttorvik: null
      };
      
      if (btItem) {
        barttorvikMatches++;
        // Add Barttorvik-specific fields
        newItem.spread_barttorvik = btItem.spread_barttorvik;
        newItem.win_prob_barttorvik = btItem.win_prob_barttorvik;
        newItem.projected_total_barttorvik = btItem.projected_total_barttorvik;
      }
      
      afterBtResult.push(newItem);
    }
    
    console.log(`Left join with Barttorvik produced ${afterBtResult.length} records with ${barttorvikMatches} Barttorvik matches`);
    
    // Now perform left join with Hasla data
    const finalResult = [];
    let haslaMatches = 0;
    
    for (const item of afterBtResult) {
      const fullHaslaKey = `${item['Team']}_${item['Home Team']}_${item['Away Team']}`;
      const swappedHaslaKey = `${item['Team']}_${item['Away Team']}_${item['Home Team']}`;
      
      // Try both orderings
      const haslaItem = haslaLookup.get(fullHaslaKey) || haslaSwappedLookup.get(swappedHaslaKey);
      
      // Always include original item and initialize Hasla fields as null
      const newItem = {
        ...item,
        spread_hasla: null,
        win_prob_hasla: null,
        projected_total_hasla: null
      };
      
      if (haslaItem) {
        haslaMatches++;
        // Add Hasla-specific fields
        newItem.spread_hasla = haslaItem.spread_hasla;
        newItem.win_prob_hasla = haslaItem.win_prob_hasla;
        newItem.projected_total_hasla = haslaItem.projected_total_hasla;
      }
      
      finalResult.push(newItem);
    }
    
    console.log(`Left join with Hasla produced ${finalResult.length} records with ${haslaMatches} Hasla matches`);
    
    // Determine the header fields from the data
    const headers = Object.keys(finalResult[0] || {}).map(id => ({id, title: id}));
    
    // Create CSV writer with the appropriate headers
    const csvWriter = createObjectCsvWriter({
      path: path.join(dataDir, 'combined_data.csv'),
      header: headers
    });

    // Write the final result to CSV
    await csvWriter.writeRecords(finalResult);
    console.log(`Successfully wrote ${finalResult.length} records to combined_data.csv`);
    
  } catch (error) {
    console.error('Error joining datasets:', error);
    throw error;
  }
}

/**
 * Main function to run all scrapers sequentially
 */
async function runScrapers() {
  try {
    console.log("=== Starting basketball data scrapers ===");
    console.log(`Data will be saved to: ${dataDir}`);
    console.log("EvanMiya output: data/em.csv");
    console.log("KenPom output: data/kp.csv");
    console.log("Barttorvik output: data/bt_mapped.csv");
    console.log("Hasla output: data/hasla_mapped.csv");
    console.log("Spreads lookup: data/spreads_lookup.csv");
    console.log("Totals lookup: data/totals_lookup.csv");
    
    // Run the EvanMiya scraper first
    await runScript(path.join(__dirname, 'scrapers', 'evanmiya-scraper.js'), 'EvanMiya');
    
    // Then run the KenPom API scraper (non-fatal - continue if it fails)
    try {
      await runScript(path.join(__dirname, 'scrapers', 'kenpom-api.js'), 'KenPom');
    } catch (err) {
      console.warn('KenPom scraper failed (non-fatal), continuing without KenPom data...');
    }
    
    // Run the EvanMiya transformer after scrapers have completed
    console.log("Running EvanMiya data transformer...");
    await transformEvanMiyaData();
    console.log("EvanMiya transformer completed successfully");
    
    // Run the team name mapping UV script
    const teamMapperScript = path.join(__dirname, 'transformers', 'map_team_names.py');
    await runUVScript(teamMapperScript, 'TeamNameMapper');
    
    // Run the Barttorvik UV script
    const bartttorvikScript = path.join(__dirname, 'scrapers', 'barttorvik.py');
    await runUVScript(bartttorvikScript, 'Barttorvik');
    
    // Run the Hasla UV script
    const haslaScript = path.join(__dirname, 'scrapers', 'hasla.py');
    await runUVScript(haslaScript, 'Hasla');
    
    // Join the datasets
    await joinDatasets();
    
    // Run the OddsAPI UV script after joining datasets (non-fatal)
    try {
      const oddsAPIScript = path.join(__dirname, 'scrapers', 'oddsAPI.py');
      await runUVScript(oddsAPIScript, 'OddsAPI');
    } catch (err) {
      console.warn('OddsAPI script failed (non-fatal), continuing...');
    }
    
    console.log("=== All scrapers and transformers completed successfully ===");
    console.log("Files created/updated:");
    console.log(`- ${path.join(dataDir, 'em.csv')}`);
    console.log(`- ${path.join(dataDir, 'kp.csv')}`);
    console.log(`- ${path.join(dataDir, 'em_mapped.csv')}`);
    console.log(`- ${path.join(dataDir, 'kp_mapped.csv')}`);
    console.log(`- ${path.join(dataDir, 'bt_mapped.csv')}`);
    console.log(`- ${path.join(dataDir, 'hasla_mapped.csv')}`);
    console.log(`- ${path.join(dataDir, 'combined_data.csv')}`);
    console.log(`- ${path.join(dataDir, 'final_combined_data.csv')} (includes spread/total probabilities from lookup tables)`);
    console.log(`- ${'CBB_Output.csv'}`);
    
  } catch (error) {
    console.error("=== Error running scrapers or transformers ===");
    console.error(error);
    process.exit(1);
  }
}

// Run the scrapers
runScrapers(); 