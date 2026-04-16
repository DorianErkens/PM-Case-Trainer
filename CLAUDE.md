# PM Case Trainer — CLAUDE.md

## Projet
Outil d'entraînement aux entretiens utilisateurs pour PMs. Un agent IA simule un utilisateur synthétique réaliste avec résistance, et génère un feedback structuré après la session.

## Stack
- Python 3.14 (venv partagé dans `/Users/dorianerkens/Desktop/AI/Code_academy/.venv`)
- Streamlit (UI)
- Anthropic API — Claude Sonnet 4.6
- Langfuse 4.3.1 (observabilité)
- Pas de base de données — Streamlit session_state uniquement

## Architecture agents
Deux agents distincts :
1. **Persona Agent** — joue le rôle de l'utilisateur synthétique pendant l'entretien
2. **Feedback Agent** — analyse la session et génère le rapport final

## User Flow
1. Contexte → l'utilisateur décrit son contexte, l'agent génère un persona (non révélé au PM)
2. Métriques → l'agent propose 3-5 métriques pertinentes, le PM valide/ajuste
3. Entretien → le PM pose ses questions, le Persona Agent répond avec résistance réaliste
4. Feedback → rapport avec pains identifiés, impact, lien métriques, score qualité

## Conventions code
- Tout le code en anglais (variables, fonctions, commentaires)
- UI Streamlit en français (langue de l'utilisateur final)
- Un fichier par agent (persona_agent.py, feedback_agent.py)
- System prompts dans un dossier /prompts

## Décisions produit prises
- Le persona N'est PAS révélé au PM avant l'entretien (découverte en live)
- Les métriques servent de grille d'évaluation pour le feedback
- Scoring basé sur : pains identifiés, profondeur des questions, lien avec les métriques
- Deux agents séparés (pas un seul agent multi-mode)

## Modèle Claude
- Claude Sonnet 4.6 (`claude-sonnet-4-6`) pour les deux agents

## Variables d'environnement (.env)
```
ANTHROPIC_API_KEY=...
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Langfuse v4 — API correcte

**IMPORTANT : l'API a changé entre v2/v3 et v4. Ne pas utiliser les anciennes formes.**

### Imports corrects
```python
from langfuse import observe, get_client   # ✅ v4
# from langfuse.decorators import observe  # ❌ n'existe plus en v4
```

### Pattern de tracing
```python
# La fonction racine @observe() devient automatiquement la trace racine
# Toutes les fonctions @observe() imbriquées deviennent des child spans

@observe(name="interview-session")        # → trace racine dans Langfuse
def run_test():
    generate_persona(...)                 # → child span automatique

@observe(name="generate-persona", as_type="chain")
def generate_persona(...):
    get_client().update_current_span(
        metadata={...},   # ✅ "metadata", PAS "attributes"
        output={...}
    )
```

### Mettre à jour le span courant
```python
get_client().update_current_span(
    metadata={...},      # ✅
    output={...},
    input={...}
)
# NE PAS utiliser attributes={} → TypeError
```

### Créer un span enfant (ex: pour chaque tool call)
```python
with get_client().start_as_current_observation(
    name="tool:reveal_pain",
    as_type="tool",
    input=tool_input
) as span:
    result = execute_tool(...)
    span.update(output=result)
# start_observation() existe mais ne set PAS le context courant
# Utiliser start_as_current_observation() pour les context managers imbriqués
```

### Plus de trace manuelle
```python
# langfuse.trace(name="...")  ❌ supprimé en v4
# Le @observe() sur la fonction racine remplace ça automatiquement
```
