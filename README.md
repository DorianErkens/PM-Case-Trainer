# PM Case Trainer — Synthetic User Interview Trainer

Un agent IA qui simule un utilisateur synthétique réaliste pour entraîner les PMs à mener des entretiens percutants et identifier les vrais pains.

> Projet construit de zéro en session de pair-programming avec Claude Code. Chaque décision technique a été discutée et expliquée avant d'être codée — l'objectif est autant de comprendre les agents IA que de construire le produit.

---

## Demo

**[→ Lancer l'app sur Streamlit Cloud](https://pm-case-trainer.streamlit.app)** *(à venir)*

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

## Interface

Layout deux colonnes — à gauche le flow principal, à droite le panneau **Agent Brain** qui montre en temps réel ce que l'agent décide à chaque question :

```
┌──────────────────────────┬─────────────────────────┐
│  ENTRETIEN               │  🧠 AGENT BRAIN          │
│                          │                          │
│  PM: "Vous pouvez me     │  → LLM call #1           │
│  donner un exemple       │  ← tool_use              │
│  concret ?"              │  🔧 flag_question         │
│                          │     {"quality":"excel..} │
│  Sophie: *pause*         │  🔧 update_resistance    │
│  "Oui, la semaine        │     7 → 5                │
│  dernière..."            │  🔧 reveal_pain(1,partial│
│                          │  👁 Pain revealed ✓      │
│                          │  → LLM call #2           │
│                          │  ← end_turn              │
└──────────────────────────┴─────────────────────────┘
```

---

## Ce que ce projet démontre techniquement

### La différence fondamentale : LLM call vs Agent

```
LLM classique :   Question → Claude → Réponse

Agent ReAct :     Question → Claude raisonne
                           → appelle un tool
                           → observe le résultat
                           → raisonne à nouveau
                           → appelle un autre tool si nécessaire
                           → répond quand il a assez d'infos
```

Sans ce pattern, Claude répondrait en une shot sans cohérence entre les tours. Avec la boucle ReAct, l'agent **construit** sa réponse étape par étape — il vérifie ce qu'il a déjà dit, ajuste sa résistance, décide ce qu'il peut révéler.

### Pourquoi deux agents séparés

| | Persona Agent | Feedback Agent |
|---|---|---|
| **Quand** | Pendant l'entretien, en temps réel | Une fois, à la fin |
| **Rôle** | Joue un personnage, résiste, révèle progressivement | Réfléchit sur la session complète |
| **Contrainte principale** | Cohérence et réalisme | Analyse objective |
| **Tools** | Actions sur l'état du persona | Calculs et agrégations |

---

## Architecture

```
PM Case Trainer/
├── app.py                    # Interface Streamlit — 4 étapes + panneau Agent Brain
├── test_agent.py             # Pipeline complet en terminal (sans UI)
├── agents/
│   ├── persona_agent.py      # Agent 1 : boucle ReAct + 4 tools + Langfuse
│   └── feedback_agent.py     # Agent 2 : boucle ReAct + 4 tools + Langfuse
├── tools/
│   ├── persona_tools.py      # Définitions JSON (ce que Claude voit) + exécuteurs Python
│   └── feedback_tools.py     # Idem pour le Feedback Agent
└── prompts/
    ├── persona_system.py     # System prompt dynamique — généré à partir du persona
    └── feedback_system.py    # System prompt avec séquence de tools explicite
```

---

## Les tools en détail

Un "tool" = une action que Claude peut **décider de prendre**. Il voit la description JSON, décide si c'est pertinent, et le code Python s'exécute côté client.

### Persona Agent — 4 tools

| Tool | Quand Claude l'appelle |
|------|----------------------|
| `reveal_pain(pain_id, level)` | La question mérite de lâcher une info (`hint` / `partial` / `full`) |
| `update_resistance(level, reason)` | Le style de question change l'ouverture du persona (1-10) |
| `check_already_revealed(pain_id)` | Avant de mentionner un pain — vérification de cohérence |
| `flag_question(quality, question, reason)` | La question est notable (`excellent` / `good` / `weak` / `closed` / `leading`) |

### Feedback Agent — 4 tools

| Tool | Ce qu'il calcule |
|------|-----------------|
| `analyze_question_patterns(focus)` | Ratio ouvertes/fermées, score de profondeur, progression |
| `identify_missed_pains()` | Pains du persona jamais surfacés par le PM |
| `match_pains_to_metrics()` | Couverture des métriques pré-définies |
| `compute_score(weights)` | Score final 0-100 pondéré (pains 40% / qualité 35% / métriques 25%) |

---

## Observabilité — Langfuse

Chaque session est tracée dans [Langfuse](https://cloud.langfuse.com) avec une hiérarchie complète :

```
interview-session             [trace racine — toute la session]
  ├── generate-persona        → 1 LLM call · persona JSON
  ├── generate-metrics        → 1 LLM call · 4 métriques
  ├── persona-turn (Q1)       → span par question PM
  │     └── react-loop        → N itérations
  │           ├── tool:flag_question       → input + observation
  │           ├── tool:check_already_revealed
  │           └── tool:reveal_pain
  ├── persona-turn (Q2) ...
  └── feedback-agent          → span final
        └── react-loop        → 4 tools d'analyse + score
```

Pattern utilisé : `@observe()` de Langfuse v4 — chaque fonction décorée devient automatiquement un child span du contexte parent.

```python
@observe(name="interview-session")      # → trace racine
def run_test():
    generate_persona(...)               # → child span automatique

@observe(name="persona-turn", as_type="agent")
def run_persona_turn(...):
    get_client().update_current_span(metadata={...})
```

---

## Stack

| Composant | Choix | Pourquoi |
|-----------|-------|----------|
| LLM | Claude Sonnet 4.6 | Meilleur équilibre nuance / coût pour simulation de persona réaliste |
| SDK | Anthropic Python SDK | Accès direct au function calling et au `stop_reason` |
| Observabilité | Langfuse 4.3+ | Open source, decorator pattern propre, dashboard complet |
| UI | Streamlit | Zéro boilerplate pour prototyper vite |
| State | Session state in-memory | Pas besoin de BDD pour le MVP |

---

## Décisions d'architecture discutées

**LangGraph vs boucle ReAct maison ?**
LangGraph aurait géré la boucle automatiquement mais l'aurait rendue invisible. On a choisi de l'écrire à la main pour comprendre exactement ce qui se passe à chaque itération — l'objectif pédagogique prime.

**Un seul agent vs deux agents ?**
Deux agents séparés — le Persona Agent joue un rôle en temps réel, le Feedback Agent réfléchit a posteriori. Les system prompts, les tools et les contraintes sont trop différents pour les mélanger.

**Langfuse vs LangSmith ?**
Langfuse est open source et s'intègre en un décorateur sur le code existant. LangSmith est natif à l'écosystème LangChain — introduit une dépendance inutile ici.

---

## Installation locale

```bash
git clone https://github.com/DorianErkens/PM-Case-Trainer.git
cd PM-Case-Trainer
pip install -r requirements.txt
cp .env.example .env   # puis remplis tes clés
streamlit run app.py
```

### Variables d'environnement

```
ANTHROPIC_API_KEY=sk-ant-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

### Tester les agents en terminal (sans UI)

```bash
python test_agent.py
```

---

## Déploiement Streamlit Cloud

1. Fork ce repo
2. Va sur [share.streamlit.io](https://share.streamlit.io) → New app
3. Sélectionne le repo · branch `main` · file `app.py`
4. **Settings → Secrets** → colle les 4 variables d'env ci-dessus

---

## Ce qu'on apprend en construisant ça

1. **Function calling** — Claude voit la description JSON, décide quand appeler le tool. C'est la description qui compte, pas le code.
2. **La boucle ReAct** — `stop_reason == "tool_use"` vs `"end_turn"` — c'est le cœur du pattern agentic.
3. **State management** — un objet mutable partagé entre tous les tools, les agents et l'UI.
4. **System prompts dynamiques** — le prompt du persona est généré à partir du persona lui-même.
5. **Multi-agent** — deux agents avec des rôles, des tools et des system prompts totalement différents.
6. **Observabilité** — tracer chaque décision de l'agent pour comprendre, débugger, et améliorer.

---

## Prochaines étapes

- [ ] Calibration du scoring selon la longueur de session
- [ ] Mode guidé vs mode libre
- [ ] Export du rapport feedback en PDF
