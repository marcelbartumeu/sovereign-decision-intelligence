# Dashboard Troubleshooting

## If `http://localhost:8000/Dashboard.HTML` doesn't work:

### 1. Check Server is Running

```bash
cd "Front end"
python3 -m http.server 8000
```

You should see:
```
Serving HTTP on 0.0.0.0 port 8000 (http://0.0.0.0:8000/) ...
```

### 2. Try Different URL Formats

- `http://localhost:8000/Dashboard.HTML` (exact case)
- `http://localhost:8000/dashboard.html` (lowercase)
- `http://127.0.0.1:8000/Dashboard.HTML`

### 3. Check Browser Console

Press **F12** (or Cmd+Option+I on Mac) and check for errors:
- Red errors in Console tab
- Network tab shows if files are loading
- Check if `scenarioData.js` loads successfully

### 4. Clear Browser Cache

- **Chrome/Edge:** Ctrl+Shift+Delete (Cmd+Shift+Delete on Mac)
- Or hard refresh: Ctrl+F5 (Cmd+Shift+R on Mac)

### 5. Check Required Files Exist

Make sure these files are in the same directory:
- `Dashboard.HTML`
- `scenarioData.js`
- `kpiData.js` (if referenced)

### 6. Check Port 8000 is Available

If port 8000 is in use, try a different port:
```bash
python3 -m http.server 8080
```
Then open: `http://localhost:8080/Dashboard.HTML`

### 7. Common Issues

**"Cannot GET /Dashboard.HTML"**
- File name case sensitivity - try lowercase: `dashboard.html`
- Or check exact filename: `ls -la Dashboard.HTML`

**Blank page**
- Check browser console for JavaScript errors
- Verify `scenarioData.js` loads (check Network tab)

**"Connect Arduino button doesn't work"**
- Must use Chrome or Edge (Web Serial API requirement)
- Check browser console for errors

### 8. Test with Simple HTML

Create `test.html`:
```html
<!DOCTYPE html>
<html>
<head><title>Test</title></head>
<body><h1>Server Works!</h1></body>
</html>
```

If `http://localhost:8000/test.html` works but Dashboard doesn't, it's a JavaScript issue.

### Still Not Working?

1. Check exact error message in browser console
2. Verify all files are in `Front end/` directory
3. Try accessing from another browser
4. Check if firewall is blocking port 8000




