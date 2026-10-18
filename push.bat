@echo off
echo ========================================================
echo   Pushing OmniPost.AI to GitHub (abhijaylg09)
echo ========================================================
git push -u origin main
if %errorlevel% equ 0 (
    echo.
    echo [SUCCESS] Code successfully pushed to GitHub!
    echo URL: https://github.com/abhijaylg09/ai-social-media-agent
) else (
    echo.
    echo [NOTE] If repository does not exist yet:
    echo 1. Go to https://github.com/new
    echo 2. Name your repository: ai-social-media-agent
    echo 3. Keep it Public or Private, do NOT check README / .gitignore
    echo 4. Click 'Create repository'
    echo 5. Run this push.bat again!
)
pause
