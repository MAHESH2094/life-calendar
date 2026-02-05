═══════════════════════════════════════════════════════════════
              LIFE CALENDAR WALLPAPER GENERATOR
                        User Guide
═══════════════════════════════════════════════════════════════

WHAT IS THIS?
─────────────
A beautiful wallpaper generator that visualizes:
  • Your Life in Weeks - See how much time you've lived/have left
  • Year Progress - Track the current year day by day
  • Goal Countdown - Countdown to any deadline/goal

The wallpaper updates automatically every day at midnight!


QUICK START
───────────
1. Run INSTALL.bat (right-click → Run as Administrator for best results)
2. Configure your settings in the GUI that opens
3. Click "Generate & Set Wallpaper"
4. Done! Wallpaper will update every day at 12:01 AM


FILES INCLUDED
──────────────
  LifeCalendar.exe         - GUI application (run anytime to change settings)
  LifeCalendarUpdate.exe   - Auto-updater (runs silently at midnight)
  life_calendar_config.json - Your saved settings
  INSTALL.bat              - One-click installer
  README.txt               - This file


CALENDAR MODES
──────────────
1. LIFE MODE
   - Shows your entire life as a grid of weeks
   - Each square = 1 week
   - Requires: Date of Birth, Expected Lifespan

2. YEAR MODE
   - Shows current year progress
   - Each square = 1 day
   - Requires: Nothing! Uses system date automatically

3. GOAL MODE
   - Countdown to any goal/deadline
   - Each square = 1 day
   - Requires: Start date, End date, Goal title


MANUAL TASK SCHEDULER SETUP
───────────────────────────
If INSTALL.bat didn't work, set up manually:

1. Press Win+R, type: taskschd.msc
2. Click "Create Basic Task"
3. Name: LifeCalendarWallpaper
4. Trigger: Daily
5. Start time: 12:01 AM
6. Action: Start a program
7. Program: Browse to LifeCalendarUpdate.exe
8. Finish


TROUBLESHOOTING
───────────────
Problem: Wallpaper not updating at midnight
Solution: Check Task Scheduler is running. Run INSTALL.bat as Administrator.

Problem: "Access Denied" error
Solution: Run INSTALL.bat as Administrator (right-click → Run as Administrator)

Problem: Wallpaper looks wrong
Solution: Open LifeCalendar.exe and set correct screen resolution

Problem: Task Scheduler says "Task failed"  
Solution: Check if life_calendar_config.json exists in same folder as EXE


TIPS
────
• Resolution Presets: Use the dropdown for quick HD/2K/4K selection
• Auto-detect: Select "Auto-detect" resolution to match your screen
• Keyboard shortcuts: Enter = Generate, Escape = Close


UNINSTALL
─────────
1. Open Task Scheduler (Win+R → taskschd.msc)
2. Delete task: LifeCalendarWallpaper
3. Delete this folder


═══════════════════════════════════════════════════════════════
                Made with ❤️ to visualize time
═══════════════════════════════════════════════════════════════
