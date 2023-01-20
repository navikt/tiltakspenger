#!/usr/bin/env bash

meta exec "cp ../template-data/Project.xml .idea/codeStyles/"
meta exec "cp ../template-data/codeStyleConfig.xml .idea/codeStyles/"
meta exec 'echo "!.idea/codeStyles/codeStyleConfig.xml" >> .gitignore'
meta exec 'echo "!.idea/codeStyles/Project.xml" >> .gitignore'
cp template-data/Project.xml .idea/codeStyles/
cp template-data/codeStyleConfig.xml .idea/codeStyles/
echo "!.idea/codeStyles/codeStyleConfig.xml" >> .gitignore
echo "!.idea/codeStyles/Project.xml" >> .gitignore
