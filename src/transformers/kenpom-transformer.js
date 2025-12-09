/**
 * KenPom Transformer
 * Transforms the manual kp.csv (root) with predicted scores into the pipeline format
 * Expected input format: date,team,opponent,side,win_prob,team_score,opp_score
 * Output format: Home Team,Away Team,Team,Game Date,spread_kenpom,win_prob_kenpom,projected_total_kenpom
 */

const fs = require('fs');
const path = require('path');
const csv = require('csv-parser');
const { createObjectCsvWriter } = require('csv-writer');

const rootDir = path.join(__dirname, '..', '..');
const inputFile = path.join(rootDir, 'kp.csv');
const outputFile = path.join(rootDir, 'data', 'kp.csv');

async function transformKenPomData() {
  console.log('Transforming KenPom data from root kp.csv...');

  // Check if input file exists
  if (!fs.existsSync(inputFile)) {
    console.warn(`KenPom source file not found at ${inputFile}, skipping transformation`);
    return;
  }

  // Read and parse the input file
  const rows = [];
  await new Promise((resolve, reject) => {
    fs.createReadStream(inputFile)
      .pipe(csv())
      .on('data', (data) => rows.push(data))
      .on('end', resolve)
      .on('error', reject);
  });

  console.log(`Read ${rows.length} rows from kp.csv`);

  // Transform to pipeline format
  const transformed = rows.map(row => {
    const homeTeam = row.side === 'home' ? row.team : row.opponent;
    const awayTeam = row.side === 'away' ? row.team : row.opponent;
    const teamScore = parseInt(row.team_score);
    const oppScore = parseInt(row.opp_score);
    const spread = oppScore - teamScore;
    const winProb = parseFloat(row.win_prob) / 100; // Convert percentage to decimal
    const projectedTotal = teamScore + oppScore;
    const gameDate = row.date.replace(/-/g, ''); // 2025-12-08 -> 20251208

    return {
      'Home Team': homeTeam,
      'Away Team': awayTeam,
      'Team': row.team,
      'Game Date': gameDate,
      'spread_kenpom': spread,
      'win_prob_kenpom': winProb,
      'projected_total_kenpom': projectedTotal
    };
  });

  // Write output
  const csvWriter = createObjectCsvWriter({
    path: outputFile,
    header: [
      { id: 'Home Team', title: 'Home Team' },
      { id: 'Away Team', title: 'Away Team' },
      { id: 'Team', title: 'Team' },
      { id: 'Game Date', title: 'Game Date' },
      { id: 'spread_kenpom', title: 'spread_kenpom' },
      { id: 'win_prob_kenpom', title: 'win_prob_kenpom' },
      { id: 'projected_total_kenpom', title: 'projected_total_kenpom' }
    ]
  });

  await csvWriter.writeRecords(transformed);
  console.log(`Transformed ${transformed.length} rows to ${outputFile}`);
}

module.exports = { transformKenPomData };

// Allow running directly
if (require.main === module) {
  transformKenPomData().catch(console.error);
}
