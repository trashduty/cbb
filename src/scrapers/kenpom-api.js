/**
 * KenPom API Scraper
 * Uses the official KenPom API to fetch FanMatch predictions
 * Replaces the web scraper to avoid Cloudflare issues
 */

require('dotenv').config();
const fs = require('fs');
const path = require('path');

const CONFIG = {
  apiKey: process.env.KENPOM_API_KEY,
  baseUrl: 'https://kenpom.com',
  outputDir: path.join(__dirname, '../../kenpom-data'),
  dataDir: path.join(__dirname, '../../data'),
  daysToFetch: 10 // Fetch predictions for the next 10 days
};

/**
 * Format date as YYYY-MM-DD for API
 */
function formatDateForApi(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
}

/**
 * Format date as YYYYMMDD for output CSV
 */
function formatDateForCsv(date) {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${year}${month}${day}`;
}

/**
 * Fetch FanMatch data for a specific date
 */
async function fetchFanMatch(date) {
  const dateStr = formatDateForApi(date);
  const url = `${CONFIG.baseUrl}/api.php?endpoint=fanmatch&d=${dateStr}`;

  console.log(`Fetching FanMatch for ${dateStr}...`);

  const response = await fetch(url, {
    method: 'GET',
    headers: {
      'Authorization': `Bearer ${CONFIG.apiKey}`,
      'Accept': 'application/json'
    }
  });

  if (!response.ok) {
    const text = await response.text();
    console.error(`API error for ${dateStr}: ${response.status} - ${text}`);
    return [];
  }

  const data = await response.json();

  if (!Array.isArray(data)) {
    console.log(`No games found for ${dateStr}`);
    return [];
  }

  console.log(`Found ${data.length} games for ${dateStr}`);
  return data;
}

/**
 * Transform API response to CSV format matching existing pipeline
 * Creates two rows per game (one for each team's perspective)
 */
function transformToCSV(games) {
  const rows = [];

  for (const game of games) {
    const homeTeam = game.Home;
    const awayTeam = game.Visitor;
    const gameDate = game.DateOfGame.replace(/-/g, ''); // Convert YYYY-MM-DD to YYYYMMDD

    // Calculate spread (positive = home favored) and total
    const homeSpread = Math.round(game.HomePred - game.VisitorPred);
    const total = Math.round(game.HomePred + game.VisitorPred);

    // HomeWP from API is an integer percentage (e.g., 86 for 86%)
    // Convert to decimal (0-1) to match existing pipeline format
    const homeWinProb = game.HomeWP / 100;
    const awayWinProb = 1 - homeWinProb;

    // Row from home team's perspective
    // Spread convention: negative means the team is favored
    rows.push({
      'Home Team': homeTeam,
      'Away Team': awayTeam,
      'Team': homeTeam,
      'Game Date': gameDate,
      'spread_kenpom': -homeSpread, // Negative spread = favored (if home is predicted to win by 8, their spread is -8)
      'win_prob_kenpom': homeWinProb,
      'projected_total_kenpom': total
    });

    // Row from away team's perspective
    rows.push({
      'Home Team': homeTeam,
      'Away Team': awayTeam,
      'Team': awayTeam,
      'Game Date': gameDate,
      'spread_kenpom': homeSpread, // Away team has opposite spread
      'win_prob_kenpom': awayWinProb,
      'projected_total_kenpom': total
    });
  }

  return rows;
}

/**
 * Write data to CSV file
 */
function writeCSV(rows, outputPath) {
  if (rows.length === 0) {
    console.log('No data to write');
    return;
  }

  const headers = Object.keys(rows[0]);
  const csvContent = [
    headers.join(','),
    ...rows.map(row => headers.map(h => row[h]).join(','))
  ].join('\n');

  fs.writeFileSync(outputPath, csvContent);
  console.log(`Wrote ${rows.length} rows to ${outputPath}`);
}

/**
 * Main function
 */
async function main() {
  console.log('KenPom API Scraper');
  console.log('==================');

  // Check for API key
  if (!CONFIG.apiKey) {
    console.error('ERROR: KENPOM_API_KEY not set in environment variables');
    process.exit(1);
  }

  console.log(`API Key: ${CONFIG.apiKey.substring(0, 8)}...`);

  // Ensure output directories exist
  if (!fs.existsSync(CONFIG.outputDir)) {
    fs.mkdirSync(CONFIG.outputDir, { recursive: true });
  }
  if (!fs.existsSync(CONFIG.dataDir)) {
    fs.mkdirSync(CONFIG.dataDir, { recursive: true });
  }

  // Fetch data for the next N days
  const allGames = [];
  const today = new Date();

  for (let i = 0; i < CONFIG.daysToFetch; i++) {
    const date = new Date(today);
    date.setDate(today.getDate() + i);

    try {
      const games = await fetchFanMatch(date);
      allGames.push(...games);
    } catch (error) {
      console.error(`Error fetching ${formatDateForApi(date)}: ${error.message}`);
    }

    // Small delay between requests to be nice to the API
    if (i < CONFIG.daysToFetch - 1) {
      await new Promise(resolve => setTimeout(resolve, 500));
    }
  }

  console.log(`\nTotal games fetched: ${allGames.length}`);

  const outputPath = path.join(CONFIG.dataDir, 'kp.csv');

  if (allGames.length === 0) {
    console.log('No games found for today (games may have already completed).');
    // Write empty CSV with headers so pipeline can continue
    const headers = 'Home Team,Away Team,Team,Game Date,spread_kenpom,win_prob_kenpom,projected_total_kenpom';
    fs.writeFileSync(outputPath, headers + '\n');
    console.log(`Wrote empty CSV with headers to ${outputPath}`);
  } else {
    // Transform and write CSV
    const csvRows = transformToCSV(allGames);
    writeCSV(csvRows, outputPath);
  }

  console.log('\nKenPom API scrape completed successfully!');
}

// Run if called directly
if (require.main === module) {
  main().catch(error => {
    console.error('Fatal error:', error);
    process.exit(1);
  });
}

module.exports = { main, fetchFanMatch, transformToCSV };
