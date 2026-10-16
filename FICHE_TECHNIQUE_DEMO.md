# Fiche technique : démo MCP + interface Gradio

**Projet :** mayerfeld-mcp-demo · **Nature :** démonstrateur pédagogique (preuve de concept), pas un produit

## 1. Contexte et finalité

Ce projet est un démonstrateur : il illustre un cas d’usage courant en entreprise, donner à un assistant IA un accès encadré aux fichiers d’une organisation, grâce à MCP (Model Context Protocol). Il a été réalisé pour expliquer MCP et le montrer en direct sur un exemple concret.

Pour expliquer MCP, la démo répond à cinq questions :

| Question | Réponse en bref |
|---|---|
| Quel problème MCP résout-il, qu'un appel d'API simple ne résout pas ? | Un protocole commun de découverte et d'appel des outils, au lieu d'une intégration sur mesure par couple application × service. Derrière un serveur MCP, il y a souvent une API classique : MCP la standardise côté IA, il ne la remplace pas |
| Serveur, client, outil ? | Le **serveur** expose des **outils** ; le **client** (dans l'application d'IA) s'y connecte et les appelle |
| Comment le modèle choisit-il un outil ? | Il reçoit les noms, descriptions et schémas des outils, et décide lui-même lequel appeler. Le protocole ne choisit pas |
| Pourquoi est-ce important pour les agents ? | Un agent boucle (raisonner, appeler un outil, observer) : MCP standardise l'étape « appeler un outil » et rend les outils réutilisables |
| « USB-C de l'IA » | Juste pour le branchement standardisé ; limitée sur la confiance et le déterminisme, car le modèle *décide* et un serveur tiers n'est pas forcément fiable |

## 2. Ce que la démo montre, et ne montre pas

| Elle montre | Elle ne montre pas |
|---|---|
| Un serveur MCP dont les outils sont découvrables par un client | Une solution prête pour des données réelles |
| Le modèle qui choisit l'outil (visible dans la trace de l'interface) | Que le modèle choisit toujours le bon outil |
| Un accès encadré : sandbox, lecture seule, limites | Une configuration de production |

## 3. Architecture en bref

Six couches (schémas détaillés dans le `README.md`) :

| Couche | Rôle |
|---|---|
| ① Présentation | Interface Gradio et ligne de commande |
| ② Application (`service.py`) | Validation, limite de débit, contrôles de lancement |
| ③ Orchestration (`agent.py`) | Boucle de l'agent avec Gemini Flash |
| ④ Protocole | Client MCP (connexion standard vers le serveur) |
| ⑤ Serveur MCP (`server.py`) | Outils et garde-fous |
| ⑥ Données (`sandbox/`) | Fichiers fictifs |

Les contenus lus par un outil sont envoyés au modèle (service externe) : seules des **données jetables** sont utilisées.

## 4. Pile technique

| Brique | Choix | Version testée |
|---|---|---|
| Langage | Python | 3.10+ |
| Protocole | SDK Python `mcp` (FastMCP) | 1.30.0 (borné `<2`) |
| Modèle | Gemini Flash (offre gratuite) | choisi via `GEMINI_MODEL` |
| SDK Google | `google-genai` | 2.30.1 |
| Interface | Gradio | 6.30.0 |
| Transport | stdio (local) | n/a |

## 5. Outils exposés

| Outil | Rôle | En lecture seule |
|---|---|---|
| `list_files` | Liste les fichiers du sandbox | oui |
| `read_file` | Lit un fichier texte | oui |
| `search_files` | Cherche un texte dans les fichiers | oui |
| `write_file` | Écrit un fichier texte (extensions et taille limitées) | non exposé |

## 6. Sécurité (résumé)

- Accès limité au dossier `sandbox/` ; tout chemin extérieur est refusé.
- Mode lecture seule par défaut dans l'interface : l'outil d'écriture n'est alors pas exposé.
- Interface en écoute locale ; mot de passe obligatoire si elle est ouverte au réseau.
- Limite de requêtes, validation des entrées, clé API jamais affichée.
- La clé API reste dans un fichier `.env` ignoré par Git.

Limites connues : le mot de passe de l'interface est une protection de base (pas de HTTPS intégré), et un fichier lu par l'agent peut contenir des instructions destinées au modèle (injection de prompt). Voir le `README.md` pour le détail.

## 7. Lancer la démo

**Ordre conseillé :** `pytest -q` (21 tests) → `python -m mayerfeld_mcp.client` (sans clé) → `mayerfeld-mcp-ui` (http://127.0.0.1:7860).

**Scénario (≈3 min) :**
1. Onglet 1 : découvrir les outils, puis lire `notes.txt` (protocole brut, sans IA).
2. Onglet 2 : « Liste mes fichiers et résume taches.md » (la trace montre que le modèle choisit).
3. Refus : lire `../pyproject.toml` (le garde-fou bloque).
4. Décocher « lecture seule », créer `test.txt`, vérifier dans l'onglet 3.



## 8. Statut des vérifications

| Élément | Statut |
|---|---|
| Serveur, outils, garde-fous, couche de service | ✅ 21 tests automatiques |
| Interface démarrée, mot de passe appliqué | ✅ testé |
| Agent Gemini en ligne de commande | ✅ testé  |
| Agent Gemini depuis l'interface web | ✅ testé  |
| Rendu dans le navigateur (Windows) | ✅ testé  |

## 9. Limites et pistes d'évolution

- Transport stdio uniquement (local) ; un déploiement distant demanderait un transport HTTP et une authentification solide.
- Nouvelle tentative automatique sur les erreurs Gemini 503 / 429 : non implémentée.
- Pas de confirmation humaine par écriture : la lecture seule joue ce rôle.
- Quotas et noms de modèles Gemini susceptibles de changer.
