# Celine

Runtime local e editável da Celine. O launcher ativo pode ser reinstalado a
partir deste checkout com o comando \`uv tool install --force --editable /home/zyltr4x/Celine\`.

O estado da agente continua isolado em \`~/.celine\`; este diretório contém
somente o código e os assets versionáveis.

Verificações rápidas:

\`celine doctor\`
\`python -m unittest discover -s /home/zyltr4x/.celine/tests -v\`
