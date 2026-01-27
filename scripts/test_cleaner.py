from smart_html_cleaner import clean_html_intelligently

with open('selenium_debug.html', 'r', encoding='utf-8') as f:
    html = f.read()

print(f'HTML length: {len(html)} chars')
result = clean_html_intelligently(html, max_length=8000)
print(f'Cleaned result length: {len(result)} chars')
print()
print('RESULT (first 2000 chars):')
print(result[:2000] if result else '(EMPTY)')

