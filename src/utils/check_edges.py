"""
Check for betting edges in Combo_Output.csv and send Discord notifications.

This script monitors Combo_Output.csv for games with positive betting edges and
"""
csv_file = os.path.join(project_root, 'Combo_Output.csv')
