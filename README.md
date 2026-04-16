# PM Case Trainer — Synthetic User Interview Trainer

Un agent IA qui simule un utilisateur synthétique réaliste pour entraîner les PMs à mener des entretiens percutants et identifier les vrais pains.

> Projet construit de zéro en session de pair-programming avec Claude Code. Chaque décision technique a été discutée et expliquée avant d'être codée.

---

## Le problème

Les PMs manquent de pratique sur les entretiens utilisateurs. Les entretiens réels sont rares, les feedbacks tardent. Il faut un environnement d'entraînement safe et réaliste.

---

## Flow produit

```
1. Contexte PM        → tu décris ton métier et ton user cible
2. Génération persona → l'agent construit un user synthétique réaliste (caché du PM)
3. Métriques          → 3-5 métriques à valider avant l'entretien
4. Entretien          → tu poses tes questions, l'agent résiste et lâche l'info progressivement
5. Feedback           → pains identifiés, score qualité, lien avec les métriques
```

---

## Ce que ce projet démontre techniquement

Ce projet est avant tout un **outil pédagogique sur les agents IA**. Il implémente le pattern **ReAct (Reason + Act)** de bout en bout, sur deux agents distincts.

### La différence fondamentale : LLM call vs Agent

```
LLM classique :   Question → Claude → Réponse

Agent ReAct :     Question → Claude raisonne
                           → appelle un tool
                           → observe le résultat
                           → raisonne à nouveau
                           → appelle un autre tool
                           → ...
                           → répond quand il a assez d'infos
```

Sans ce pattern, Claude répondrait en une shot sans "agir" ni "observer". Avec la boucle ReAct, l'agent **construit** sa réponse étape par étape, comme un humain qui vérifie ses notes avant de parler.

### Ce que ça change concrètement dans ce produit

Le Persona Agent, avant chaque réponse, peut :
1. Vérifier si ce pain a déjà été révélé → cohérence sur toute la session
2. Évaluer si la question mérite qu'il s'ouvre → résistance dynamique
3. Révéler une info au bon niveau de détail → réalisme de l'entretien
4. Logger la qualité de la question → données pour le feedback

Sans la boucle, il devine. Avec la boucle, il agit et observe.

---

## Architecture

```
PM Case Trainer/
├── test_agent.py             # Pipeline complet en terminal (persona → métriques → entretien → feedback)
├── agents/
│   ├── persona_agent.py      # Agent 1 : joue le user synthétique avec boucle ReAct
│   └── feedback_agent.py     # Agent 2 : analyse la session et génère le rapport
├── tools/
│   ├── persona_tools.py      # 4 tools du Persona Agent (définitions JSON + exécuteurs Python)
│   └── feedback_tools.py     # 4 tools du Feedback Agent
└── prompts/
    ├── persona_system.py     # System prompt dynamique — généré à partir du persona
    └── feedback_system.py    # System prompt du Feedback Agent
```

### Deux agents, deux rôles

| Agent | Rôle | Quand |
|-------|------|-------|
| **Persona Agent** | Joue le user synthétique en temps réel, résiste, révèle progressivement | Pendant l'entretien |
| **Feedback Agent** | Analyse toute la session, score les questions, génère le rapport | Une fois l'entretien terminé |

---

## Les tools en détail

Un "tool" = une action que Claude peut **décider de prendre**. Il voit la description en JSON, décide si c'est pertinent, et le code Python s'exécute côté client.

### Persona Agent tools

| Tool | Quand Claude l'appelle |
|------|----------------------|
| `reveal_pain(pain_id, level)` | La question du PM mérite qu'on lâche une info (`hint` / `partial` / `full`) |
| `update_resistance(level, reason)` | Le style de question change l'ouverture du persona (1-10) |
| `check_already_revealed(pain_id)` | Avant de mentionner un pain — vérification de cohérence |
| `flag_question(quality, question, reason)` | La question est notable (`excellent` / `good` / `weak` / `closed` / `leading`) |

### Feedback Agent tools

| Tool | Ce qu'il calcule |
|------|-----------------|
| `analyze_question_patterns(focus)` | Ratio ouvertes/fermées, score de profondeur, progression |
| `identify_missed_pains()` | Pains du persona jamais surfacés par le PM |
| `match_pains_to_metrics()` | Couverture des métriques pré-définies |
| `compute_score(weights)` | Score final 0-100 pondéré (pains / qualité / métriques) |

---

## Observabilité — Langfuse

Chaque session est tracée dans [Langfuse](https://cloud.langfuse.com) avec une hiérarchie complète :

```
interview-session  [trace racine]
  ├── generate-persona      → 1 LLM call, tokens, persona généré
  ├── generate-metrics      → 1 LLM call, 4 métriques
  ├── persona-turn (Q1)     → span par question
  │     └── react-loop      → iterations, tool calls, observations
  │           ├── tool:flag_question
  │           ├── tool:check_already_revealed
  │           └── tool:reveal_pain
  ├── persona-turn (Q2) ...
  └── feedback-agent        → span final
        └── react-loop      → 4 tools d'analyse + score
```

Le panneau debug visible dans l'UI (à venir) reprend cette même structure en temps réel.

**Pattern utilisé :** `@observe()` de Langfuse v4 — chaque fonction décorée devient automatiquement un span enfant du span parent.

```python
@observe(name="interview-session")   # → trace racine
def run_test():
    generate_persona(...)            # → child span automatique

@observe(name="persona-turn", as_type="agent")
def run_persona_turn(...):
    _react_loop(...)                 # → child span de persona-turn
```

---

## Stack

| Composant | Choix | Pourquoi |
|-----------|-------|----------|
| LLM | Claude Sonnet 4.6 | Meilleur équilibre nuance / coût pour simulation de persona |
| SDK | Anthropic Python SDK | Accès direct au function calling et au stop_reason |
| Observabilité | Langfuse 4.3+ | Open source, decorator pattern propre, dashboard complet |
| UI | Streamlit *(à venir)* | Zéro boilerplate pour prototyper vite |
| State | Session state in-memory | Pas besoin de BDD pour le MVP |

---

## Décisions d'architecture discutées

**LangGraph vs boucle ReAct maison ?**
LangGraph aurait géré la boucle automatiquement mais l'aurait rendue invisible. On a choisi de l'écrire à la main pour comprendre exactement ce qui se passe à chaque itération.

**Un seul agent vs deux agents ?**
Deux agents séparés — le Persona Agent joue un rôle en temps réel, le Feedback Agent réfléchit a posteriori sur la session complète. Les system prompts, les tools et les contraintes sont trop différents pour les mélanger.

**Langfuse vs LangSmith ?**
Langfuse est open source et s'intègre en un décorateur sur le code existant. LangSmith est natif à LangGraph mais introduit une dépendance forte à l'écosystème LangChain.

---

## Installation

```bash
git clone https://github.com/DorianErkens/PM-Case-Trainer.git
cd PM-Case-Trainer
pip install -r requirements.txt
```

Crée un fichier `.env` :
```
ANTHROPIC_API_KEY=sk-ant-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

## Lancer le pipeline complet en terminal

```bash
python test_agent.py
```

Output terminal :
```
STEP 1 — Persona Generation       → persona JSON (caché du PM)
STEP 2 — Metrics                  → 4 métriques proposées
STEP 3 — Interview (ReAct loop)   → chaque question avec AGENT BRAIN visible
  [PM - Q3] Quand vous dites...
  [AGENT BRAIN]
    → LLM call #1
    ← tool_use  (2196in / 177out tokens)
    🔧 flag_question  {"quality": "excellent", ...}
    🔧 update_resistance  {"new_level": 5, ...}
    🔧 reveal_pain  {"pain_id": 1, "reveal_level": "partial"}
    → LLM call #2
    ← end_turn
  [PERSONA] *réfléchit* Ouais, y'en a une...
STEP 4 — Feedback Report          → rapport + score /100
```

---

## Ce qu'on apprend en construisant ça

1. **Function calling** — comment Claude décide quel tool appeler et pourquoi (la description compte plus que le code)
2. **La boucle ReAct** — `stop_reason == "tool_use"` vs `"end_turn"` — c'est le coeur du pattern
3. **State management** — l'état mutable partagé entre tools, agent et UI
4. **System prompts dynamiques** — le prompt du persona est généré à partir du persona lui-même
5. **Multi-agent** — deux agents avec des rôles, des tools et des system prompts totalement différents
6. **Observabilité** — tracer chaque décision de l'agent pour comprendre et débugger

---

## Prochaines étapes

- [ ] Interface Streamlit avec panneau "Agent Brain" en temps réel
- [ ] Feedback Agent — rapport interactif avec drill-down par pain
- [ ] Mode libre (le PM pose ses propres questions) vs mode guidé
