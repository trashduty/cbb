/**
 * EvanMiya Data Transformer
 * 
 * This script transforms the raw EvanMiya CSV data to a consistent format
 * that matches the KenPom data format. It takes one row per game and creates
 * two rows, one from each team's perspective.
 */

const fs = require('fs');
const path = require('path');
const csv = require('csv-parser');
const { createObjectCsvWriter } = require('csv-writer');
const os = require('os');
require('dotenv').config();

// Configure the input and output paths
const config = {
  inputFile: path.join(__dirname, '../../data/em.csv'),
  outputFile: path.join(os.tmpdir(), 'em_temp.csv')
};

/**
 * Transforms EvanMiya data from one row per game to two rows per game (one for each team)
 */
async function transformEvanMiyaData() {
  console.log(`Starting transformation of EvanMiya data from ${config.inputFile}`);

  // Check if the input file exists
  if (!fs.existsSync(config.inputFile)) {
    console.error(`Input file not found: ${config.inputFile}`);
    process.exit(1);
  }

  // Array to hold the transformed data
  const transformedData = [];

  // Read the CSV file and transform the data
  return new Promise((resolve, reject) => {
    fs.createReadStream(config.inputFile)
      .pipe(csv())
      .on('data', (row) => {
        // Each row represents a game between home and away teams
        const homeTeam = row.home;
        const awayTeam = row.away;
        const gameDate = row.Date || new Date().toISOString().split('T')[0];

        // Try both team orderings and use the one that matches the line
        const line = parseFloat(row.line);
        const isHomeTeamFavored = line < 0;

        // Create records with original team ordering
        const homeRow = {
          'Home Team': homeTeam,
          'Away Team': awayTeam,
          'Team': homeTeam,
          'Game Date': gameDate,
          'spread_evanmiya': -line, // Flip the sign for home team
          'win_prob_evanmiya': parseFloat(row.home_win_prob),
          'projected_total_evanmiya': parseFloat(row.ou)
        };

        const awayRow = {
          'Home Team': homeTeam,
          'Away Team': awayTeam,
          'Team': awayTeam,
          'Game Date': gameDate,
          'spread_evanmiya': line,
          'win_prob_evanmiya': parseFloat(row.away_win_prob),
          'projected_total_evanmiya': parseFloat(row.ou)
        };

        // Create records with swapped team ordering
        const swappedHomeRow = {
          'Home Team': awayTeam,
          'Away Team': homeTeam,
          'Team': awayTeam,
          'Game Date': gameDate,
          'spread_evanmiya': line,
          'win_prob_evanmiya': parseFloat(row.away_win_prob),
          'projected_total_evanmiya': parseFloat(row.ou)
        };

        const swappedAwayRow = {
          'Home Team': awayTeam,
          'Away Team': homeTeam,
          'Team': homeTeam,
          'Game Date': gameDate,
          'spread_evanmiya': -line,
          'win_prob_evanmiya': parseFloat(row.home_win_prob),
          'projected_total_evanmiya': parseFloat(row.ou)
        };

        // Add both versions to allow for flexible matching
        transformedData.push(homeRow, awayRow, swappedHomeRow, swappedAwayRow);
      })
      .on('end', async () => {
        console.log(`Read ${transformedData.length / 4} games (${transformedData.length} rows)`);

        // Create CSV writer with the appropriate headers
        const csvWriter = createObjectCsvWriter({
          path: config.outputFile,
          header: [
            { id: 'Home Team', title: 'Home Team' },
            { id: 'Away Team', title: 'Away Team' },
            { id: 'Team', title: 'Team' },
            { id: 'Game Date', title: 'Game Date' },
            { id: 'spread_evanmiya', title: 'spread_evanmiya' },
            { id: 'win_prob_evanmiya', title: 'win_prob_evanmiya' },
            { id: 'projected_total_evanmiya', title: 'projected_total_evanmiya' }
          ]
        });

        try {
          // Write the transformed data to the temporary file
          await csvWriter.writeRecords(transformedData);
          console.log(`Transformed data written to temporary file`);

          // Copy the transformed file back to the original
          fs.copyFileSync(config.outputFile, config.inputFile);
          console.log(`Original file updated with transformed data: ${config.inputFile}`);

          // Clean up temporary file
          fs.unlinkSync(config.outputFile);
          
          resolve({
            success: true,
            inputFile: config.inputFile,
            gameCount: transformedData.length / 4,
            rowCount: transformedData.length
          });
        } catch (error) {
          console.error('Error writing transformed data:', error);
          reject(error);
        }
      })
      .on('error', (error) => {
        console.error('Error reading CSV file:', error);
        reject(error);
      });
  });
}

// Run the transformer if this script is run directly
if (require.main === module) {
  transformEvanMiyaData()
    .then(result => {
      console.log('Transformation complete!');
      process.exit(0);
    })
    .catch(error => {
      console.error('Transformation failed:', error);
      process.exit(1);
    });
}

module.exports = { transformEvanMiyaData }; 