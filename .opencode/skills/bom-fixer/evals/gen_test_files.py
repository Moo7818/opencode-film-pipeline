import os

test_dir = os.path.join(os.path.dirname(__file__), 'files')
os.makedirs(test_dir, exist_ok=True)

# 1. 带 BOM 的 JSON 文件
bom = b'\xef\xbb\xbf'
json_content = '{"name": "测试", "value": 42}'.encode('utf-8')
with open(os.path.join(test_dir, 'bom_test.json'), 'wb') as f:
    f.write(bom + json_content)

# 2. 带 BOM 的 MD 文件
md_content = '# 测试文档\n\n这是一段测试内容。'.encode('utf-8')
with open(os.path.join(test_dir, 'bom_test.md'), 'wb') as f:
    f.write(bom + md_content)

# 3. 无 BOM 的 JSON（对照）
with open(os.path.join(test_dir, 'clean_test.json'), 'wb') as f:
    f.write(json_content)

# 4. 无 BOM 的 MD（对照）
with open(os.path.join(test_dir, 'clean_test.md'), 'wb') as f:
    f.write(md_content)

print(f"✅ 测试文件已生成到 {test_dir}")
for f in sorted(os.listdir(test_dir)):
    fp = os.path.join(test_dir, f)
    with open(fp, 'rb') as fh:
        head = fh.read(3)
    has_bom = 'BOM' if head == b'\xef\xbb\xbf' else '无BOM'
    print(f"  {has_bom}: {f} ({os.path.getsize(fp)} bytes)")