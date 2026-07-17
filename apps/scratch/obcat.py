import os
import pathlib
import glob

vault_path = pathlib.Path("C:/Users/Admin/Documents/Corbimimateryiam")

contents = []
for file in glob.glob("Intake/Emotion - *", root_dir=vault_path):
    with open(vault_path.joinpath(file)) as f:
        new_content = f"## {file[file.find('-')+1:-3]}\n\n{f.read()}"
        contents.append(new_content)

with open('var/emotions.md', 'w') as f:
    f.write('\n\n'.join(contents))