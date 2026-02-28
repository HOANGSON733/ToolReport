# TODO: Fix Chrome Driver Initialization Error

## Issue Description
- Error: `'NoneType' object has no attribute 'get'`
- Cause: `create_chrome_driver()` function returns `None` when Chrome driver initialization fails
- Impact: Application crashes when trying to use the driver

## Root Cause Analysis
- The function `create_chrome_driver()` can return `None` if Chrome driver initialization fails
- Code later calls `.get()` method on the driver without checking if it's `None`
- No fallback mechanism when driver creation fails

## Solution Implemented
- [x] Added try-except block in `create_chrome_driver()` to use ChromeDriverManager as fallback
- [x] Modified driver initialization logic to attempt ChromeDriverManager if direct initialization fails
- [x] Added proper error handling to prevent `None` return values

## Testing
- [ ] Test Chrome driver initialization with different scenarios
- [ ] Verify fallback mechanism works when direct driver creation fails
- [ ] Check that application doesn't crash when driver creation fails

## Files Modified
- [x] `Search_keyword.py` - Updated `create_chrome_driver()` function with fallback logic

## Next Steps
- [ ] Run test script to verify the fix works
- [ ] Monitor for any new issues related to driver initialization
- [ ] Consider adding more robust error handling and logging
