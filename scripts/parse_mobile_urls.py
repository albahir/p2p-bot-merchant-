import re

with open('C:/Users/jonan/.gemini/antigravity/brain/90b307b8-344c-43b6-b4a7-dab3f0abd0d4/.system_generated/tasks/task-7506.log', 'r', encoding='utf-8') as f:
    text = f.read()

urls = re.findall(r'https://stitch\.googleapis\.com/v1/projects/[0-9]+/files/[a-zA-Z0-9]+:download', text)
print("Unique URLs found in task-7506:")
for u in set(urls):
    print(u)
