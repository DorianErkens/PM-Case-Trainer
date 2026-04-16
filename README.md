# PM Case Trainer — Synthetic User Interview Trainer

Un agent IA qui simule un utilisateur synthétique réaliste pour entraîner les PMs à mener des entretiens percutants.

---

## Ce que ce projet démontre

Ce projet est avant tout un **outil pédagogique sur les agents IA**. Il implémente le pattern **ReAct (Reason + Act)** — la base de tout agent avec prise de décision réelle.

### Le pattern ReAct en pratique

```
Question PM
    ↓
Claude réfléchit
    ↓
Claude appelle un tool (ex: check_already_revealed)
    ↓
On exécute le tool → observation
    ↓
Claude lit l'observation et décide quoi faire ensuite
    ↓
... boucle jusqu'à "end_turn"
    ↓
Réponse finale du persona
```

Sans ce pattern, Claude répondrait en une shot sans "agir" ni "observer". Avec ce pattern, l'agent **construit** sa réponse étape par étape comme un humain qui vérifie ses notes avant de parler.

---

## Flow produit

```
1. Contexte PM        → tu décris ton métier et ton user cible
2. Génération persona → l'agent construit un user synthétique (caché du PM)
3. Métriques          → 3-5 métriques à valider avant l'entretien
4. Entretien          → tu poses tes questions, l'agent résiste et lâche l'info progressivement
5. Feedback           → pains identifiés, score qualité, lien avec les métriques
```

---

## Architecture

```
PM Case Trainer/
├── app.py                    # Interface Streamlit (à venir)
├── test_agent.py             # Test terminal de la boucle ReAct
├── agents/
│   ├── persona_agent.py      # Agent 1 : joue le user avec boucle ReAct
│   └── feedback_agent.py     # Agent 2 : génère le rapport final (à venir)
├── tools/
│   ├── persona_tools.py      # Tools du Persona Agent (actions + exécuteurs)
│   └── feedback_tools.py     # Tools du Feedback Agent (à venir)
└── prompts/
    ├── persona_system.py     # System prompt dynamique du persona
    └── feedback_system.py    # System prompt du feedback (à venir)
```

### Deux agents distincts

| Agent | Rôle | Tools |
|-------|------|-------|
| **Persona Agent** | Joue le user synthétique avec résistance réaliste | `reveal_pain`, `update_resistance`, `check_already_revealed`, `flag_question` |
| **Feedback Agent** | Analyse la session et génère le rapport | `analyze_questions`, `match_pains_to_metrics`, `compute_score` |

---

## Tools du Persona Agent

Un "tool" = une action que Claude peut décider de prendre. Il voit la description, décide si c'est pertinent, et toi tu exécutes le code Python.

| Tool | Quand Claude l'appelle |
|------|----------------------|
| `reveal_pain(pain_id, level)` | La question du PM mérite qu'on lâche une info |
| `update_resistance(level, reason)` | Le style de question change l'ouverture du persona |
| `check_already_revealed(pain_id)` | Avant de mentionner un pain — vérification de cohérence |
| `flag_question(quality, question, reason)` | La question est notable (bonne ou mauvaise) |

---

## Stack

- **Python 3.11+**
- **Anthropic SDK** — Claude Sonnet 4.6
- **Streamlit** — interface (à venir)
- **Pas de base de données** — `session_state` Streamlit pour le MVP

---

## Installation

```bash
git clone https://github.com/DorianErkens/PM-Case-Trainer.git
cd PM-Case-Trainer
pip install -r requirements.txt
cp .env.example .env  # puis ajoute ta clé ANTHROPIC_API_KEY
```

## Tester l'agent en terminal

```bash
python test_agent.py
```

Tu verras en output :
- La génération du persona (caché du PM)
- Les métriques proposées
- 3 questions simulées avec **la boucle ReAct complète** (chaque LLM call, chaque tool call, chaque observation)
- L'état final de la session

---

## Ce qu'on apprend en construisant ça

1. **Function calling** — comment Claude décide quel tool appeler et quand
2. **La boucle ReAct** — Reason → Act → Observe → repeat
3. **State management** — l'état du persona évolue au fil de la conversation
4. **System prompts dynamiques** — le prompt change selon le persona généré
5. **Multi-agent** — deux agents avec des rôles et des tools différents
