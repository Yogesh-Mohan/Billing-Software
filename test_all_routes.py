"""Deep template and logic bug scanner"""
import os, sys, re
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

bugs = []

# 1. Check all templates for common Jinja2 issues
template_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates')
for fname in os.listdir(template_dir):
    if not fname.endswith('.html'):
        continue
    fpath = os.path.join(template_dir, fname)
    with open(fpath, 'r', encoding='utf-8') as f:
        content = f.read()
        lines = content.split('\n')
    
    for i, line in enumerate(lines, 1):
        # Check for sum filter with default= (the bug we just fixed)
        if 'sum(' in line and 'default=' in line:
            bugs.append(f"[TEMPLATE] {fname}:{i} - Jinja2 sum() with invalid 'default=' param (use 'start=' instead)")
        
        # Check for .items on invoice dict (conflicts with dict.items())
        if re.search(r'invoice\.items\b', line) and 'invoice[' not in line:
            # Only flag if it's in a for loop or filter, not in dict access context
            if 'for ' in line or '|' in line or 'set ' in line:
                bugs.append(f"[TEMPLATE] {fname}:{i} - 'invoice.items' may conflict with dict.items() method. Use invoice['items'] instead")
        
        # Check for .strftime without safety check
        if '.strftime(' in line and 'if ' not in line and '{%' not in line:
            # Check if the variable could be None
            m = re.search(r'(\w+(?:\.\w+)*)\.strftime', line)
            if m:
                var = m.group(1)
                # Check if this line has a truthy check
                if f'if {var}' not in content[max(0, content.find(line)-200):content.find(line)+len(line)]:
                    pass  # Many are fine, just note potential issues

        # Check for missing 'discount_pct' or 'discount_amount' access without safety
        if 'discount_amount' in line and 'is defined' not in line and 'get(' not in line and 'if ' not in line:
            if '{{' in line:
                bugs.append(f"[TEMPLATE] {fname}:{i} - 'discount_amount' accessed without safety check (may be missing on old invoices)")

# 2. Check file_db.py for missing aggregate operations
print("=" * 60)
print("CHECKING file_db.py FOR MISSING AGGREGATE SUPPORT")
print("=" * 60)

fdb_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'file_db.py')
with open(fdb_path, 'r', encoding='utf-8') as f:
    fdb_content = f.read()

app_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'app.py')
with open(app_path, 'r', encoding='utf-8') as f:
    app_content = f.read()

# Find all aggregate operations used in app.py
agg_ops_used = set(re.findall(r'"\$(\w+)"', app_content))
# Find all aggregate operations handled in file_db.py
agg_ops_supported = set()
if '$match' in fdb_content: agg_ops_supported.add('match')
if '$group' in fdb_content: agg_ops_supported.add('group')
if '$sort' in fdb_content: agg_ops_supported.add('sort')
if '$limit' in fdb_content: agg_ops_supported.add('limit')
if '$addFields' in fdb_content: agg_ops_supported.add('addFields')
if '$unwind' in fdb_content: agg_ops_supported.add('unwind')
if '$first' in fdb_content: agg_ops_supported.add('first')
if '$toInt' in fdb_content: agg_ops_supported.add('toInt')
if '$sum' in fdb_content: agg_ops_supported.add('sum')
if '$dateToString' in fdb_content: agg_ops_supported.add('dateToString')

# Common aggregate ops used in app.py
needed_ops = {'match', 'group', 'sort', 'limit', 'addFields', 'unwind', 'first', 'sum', 'toInt', 'dateToString'}
app_agg_ops = agg_ops_used & needed_ops

print(f"  Aggregate ops used in app.py: {sorted(app_agg_ops)}")
print(f"  Aggregate ops supported in file_db.py: {sorted(agg_ops_supported)}")

missing = app_agg_ops - agg_ops_supported
if missing:
    for op in missing:
        bugs.append(f"[FILE_DB] Missing aggregate support for '${op}' - used in app.py but not in file_db.py")
    print(f"  MISSING: {sorted(missing)}")
else:
    print(f"  All ops covered!")

# 3. Check for potential issues in app.py
print("\n" + "=" * 60)
print("CHECKING app.py FOR LOGIC BUGS")
print("=" * 60)

lines = app_content.split('\n')
for i, line in enumerate(lines, 1):
    # Check for bare except clauses (swallows all errors)
    if re.search(r'^\s*except\s*:', line):
        bugs.append(f"[APP] app.py:{i} - Bare 'except:' clause swallows all errors silently")
    
    # Check for unhandled ObjectId conversions
    if 'ObjectId(' in line and 'try' not in lines[max(0,i-3):i][-1] if i > 3 else True:
        pass  # Many are inside try blocks

# 4. Check for missing $unwind in file_db aggregate
print("\n" + "=" * 60)
print("CHECKING $unwind and $first SUPPORT")
print("=" * 60)

# Search for $unwind usage in app.py
unwind_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if 'unwind' in l.lower()]
first_lines = [(i, l.strip()) for i, l in enumerate(lines, 1) if 'first' in l.lower() and '$' in l]

if unwind_lines:
    print("  $unwind used in app.py at:")
    for ln, content in unwind_lines:
        print(f"    Line {ln}: {content[:80]}")
    if 'unwind' not in agg_ops_supported:
        bugs.append("[FILE_DB] $unwind is used in app.py (reports) but NOT supported in file_db.py aggregate()")

if first_lines:
    print("  $first used in app.py at:")
    for ln, content in first_lines:
        print(f"    Line {ln}: {content[:80]}")
    if 'first' not in agg_ops_supported:
        bugs.append("[FILE_DB] $first is used in app.py (reports) but NOT supported in file_db.py aggregate()")

# 5. Check for missing static files
print("\n" + "=" * 60)
print("CHECKING STATIC FILES")
print("=" * 60)

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')
js_dir = os.path.join(static_dir, 'js')
css_dir = os.path.join(static_dir, 'css')

for d, name in [(js_dir, 'static/js'), (css_dir, 'static/css')]:
    if os.path.exists(d):
        files = os.listdir(d)
        print(f"  {name}/: {files}")
    else:
        print(f"  {name}/: MISSING!")
        bugs.append(f"[STATIC] Directory '{name}' is missing")

# Check if main.js exists (referenced in base.html)
main_js = os.path.join(js_dir, 'main.js')
if not os.path.exists(main_js):
    bugs.append("[STATIC] main.js referenced in base.html but doesn't exist")
    print("  WARNING: main.js is MISSING!")
else:
    print(f"  main.js exists ({os.path.getsize(main_js)} bytes)")

# 6. Check uploads directory
uploads_dir = os.path.join(static_dir, 'uploads')
if os.path.exists(uploads_dir):
    files = os.listdir(uploads_dir)
    print(f"  uploads/: {len(files)} files")
else:
    print("  uploads/: Will be created at runtime")

# Print all bugs
print("\n" + "=" * 60)
print(f"BUGS FOUND: {len(bugs)}")
print("=" * 60)
for i, bug in enumerate(bugs, 1):
    print(f"  {i}. {bug}")

if not bugs:
    print("  No bugs found!")
