# PM Case Trainer — CLAUDE.md

## Projet
Outil d'entraînement aux entretiens utilisateurs pour PMs. Un agent IA simule un utilisateur synthétique réaliste avec résistance, et génère un feedback structuré après la session.

## Stack
- Python 3.11+
- Streamlit (UI)
- Anthropic API (Claude)
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

## Modèle Claude
- À définir (en cours d'évaluation)

## Clé API
- Variable d'environnement : ANTHROPIC_API_KEY
