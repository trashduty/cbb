# Direct Links to Analysis Files

## Important Note 🔔

The analysis files are currently in the **Pull Request branch** and not yet merged into the main branch. This is why you don't see them when browsing the repository normally.

**Branch name:** `copilot/create-moneyline-analysis-script`

## How to Access the Files

### Option 1: View in Pull Request (Recommended)

Once the PR is created, you can view all changes at:
- **Pull Request URL:** https://github.com/trashduty/cbb/pulls

Look for the PR titled: "Create comprehensive EM+BT moneyline analysis script"

### Option 2: View Files Directly on GitHub (PR Branch)

Click these links to view each file in the PR branch:

#### 📊 Main Analysis Report
**EM+BT Moneyline Analysis Report:**
- https://github.com/trashduty/cbb/blob/copilot/create-moneyline-analysis-script/analysis/reports/em_bt_moneyline_analysis.md

#### 🐍 Analysis Script
**Python Script to Generate Analysis:**
- https://github.com/trashduty/cbb/blob/copilot/create-moneyline-analysis-script/analysis/scripts/em_bt_moneyline_analysis.py

#### 💾 Detailed Data Export
**CSV with 894 Games:**
- https://github.com/trashduty/cbb/blob/copilot/create-moneyline-analysis-script/analysis/data/em_bt_moneyline_results.csv

#### 📖 Documentation
**README with Instructions:**
- https://github.com/trashduty/cbb/blob/copilot/create-moneyline-analysis-script/analysis/README.md

### Option 3: Browse the Branch on GitHub

Navigate to the branch to see all files:
1. Go to https://github.com/trashduty/cbb
2. Click the branch dropdown (shows "main" by default)
3. Select: `copilot/create-moneyline-analysis-script`
4. Navigate to: `analysis/` folder

### Option 4: View in Your Local Repository

If you have the repository cloned locally:

```bash
# Switch to the PR branch
git fetch origin
git checkout copilot/create-moneyline-analysis-script

# View the files
ls -la analysis/reports/
cat analysis/reports/em_bt_moneyline_analysis.md
```

## After the PR is Merged

Once the Pull Request is merged into the main branch, these files will be available at:

#### Main Analysis Report (after merge)
- https://github.com/trashduty/cbb/blob/main/analysis/reports/em_bt_moneyline_analysis.md

#### Analysis Script (after merge)
- https://github.com/trashduty/cbb/blob/main/analysis/scripts/em_bt_moneyline_analysis.py

#### Data Export (after merge)
- https://github.com/trashduty/cbb/blob/main/analysis/data/em_bt_moneyline_results.csv

#### Documentation (after merge)
- https://github.com/trashduty/cbb/blob/main/analysis/README.md

## Quick Preview

Here's what's in the analysis report:

### Key Findings
- **894 games analyzed**
- **Best ROI:** +35.9% at 4%+ edge threshold (48 games)
- **Most Profitable Band:** 11-20% market probability (+185.2% ROI)
- **Bands to Avoid:** 31-60% probability range

### Report Sections
1. TL;DR summary with key ROI numbers
2. Overall performance by edge threshold (0%, 1%, 2%, 3%, 4%)
3. Performance by win probability bands (10% buckets)
4. Key insights and recommendations
5. Recommended betting strategy
6. Comparison to KP+BT model
7. Detailed methodology

## Files Checklist

In the PR branch:
- ✅ `analysis/README.md` - Documentation for accessing reports
- ✅ `analysis/reports/em_bt_moneyline_analysis.md` - Main analysis report
- ✅ `analysis/scripts/em_bt_moneyline_analysis.py` - Analysis script
- ✅ `analysis/data/em_bt_moneyline_results.csv` - Detailed data (894 games)

## Need Help?

If you still can't access the files:
1. Check that you're viewing the correct branch: `copilot/create-moneyline-analysis-script`
2. Wait for the PR to be merged to main branch
3. Or use the direct links provided above

## To Merge the PR

If you have repository permissions:
1. Go to https://github.com/trashduty/cbb/pulls
2. Find the PR: "Create comprehensive EM+BT moneyline analysis script"
3. Review the changes
4. Click "Merge pull request"
5. Files will then appear in the main branch

---

**Note:** All links above point to the PR branch (`copilot/create-moneyline-analysis-script`). If you see a 404 error, the branch may not have been pushed yet, or the PR hasn't been created.
