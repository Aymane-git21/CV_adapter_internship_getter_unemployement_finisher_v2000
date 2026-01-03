import os

# Read the template
with open('CoverLetter.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# Simulate app.py injection logic using the commands app.py generates
dummy_body = r"""
\subject{\textbf{Objet :} Candidature Test Simulé}

\opening{Madame, Monsieur,}

Ceci est un test pour vérifier que le contenu généré par l'app (qui utilise opening et closing) s'affiche correctement et qu'il n'y a plus de duplication.

\lipsum[1-2]

\closing{Cordialement,}
"""

if "% <BODY_CONTENT>" in content:
    print("Placeholder found. Injecting content...")
    final_content = content.replace("% <BODY_CONTENT>", dummy_body)
else:
    print("Placeholder NOT found. Appending content (BAD)...")
    final_content = content.replace("\\end{document}", f"\n{dummy_body}\n\\end{{document}}")

# Write to a test file
with open('CoverLetter_Simulated.tex', 'w', encoding='utf-8') as f:
    f.write(final_content)

print("Created CoverLetter_Simulated.tex")
