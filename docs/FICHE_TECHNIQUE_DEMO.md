# Fiche technique : démo MCP + interface Gradio

**Projet :** mayerfeld-mcp-demo · **Pour :** mayerfeld.consulting

## 1. Objectif
Montrer en direct comment un modèle (Gemini Flash) découvre et appelle des outils via MCP, avec une interface web pour tester chaque brique.

## 2. Pile technique et versions testées
| Brique | Choix | Version testée |
|---|---|---|
| Langage | Python | 3.10+ (3.11 Windows, 3.12 Linux) |
| Protocole | MCP, SDK Python `mcp` (FastMCP) | 1.30.0 (borné `<2`) |
| Modèle | Gemini Flash, offre gratuite | modèle choisi via `GEMINI_MODEL` |
| SDK Google | `google-genai` | 2.30.1 |
| Interface | Gradio | 6.30.0 |
| Transport | stdio (local) | n/a |

## 3. Architecture en une phrase
Une interface (ou la ligne de commande) pilote un **hôte** qui parle à Gemini et à un **client MCP** ; le client lance un **serveur MCP** qui n'accède qu'au dossier `sandbox/`.

## 4. Outils exposés
| Outil | Rôle | Disponible en lecture seule |
|---|---|---|
| `list_files` | Liste les fichiers du sandbox | oui |
| `read_file` | Lit un fichier texte (≤ 100 Ko) | oui |
| `search_files` | Cherche un texte dans les fichiers | oui |
| `write_file` | Écrit `.txt .md .json .csv` (≤ 100 Ko) | **non** (non exposé) |

## 5. Sécurité
| Risque | Parade |
|---|---|
| Sortie du sandbox (`../`, liens symboliques) | `_safe()` résout le chemin et refuse tout ce qui sort |
| Écriture de fichiers dangereux | Extensions autorisées + taille max |
| Modèle qui écrit sans contrôle | Mode lecture seule par défaut dans l'UI : l'outil n'existe pas |
| Accès non autorisé à l'UI | Écoute locale par défaut ; mot de passe obligatoire hors local |
| Abus du quota gratuit | 10 appels agent par minute |
| Fuite de la clé API | Clé dans `.env` (ignoré par Git), jamais affichée, masquée dans les erreurs |
| Injection de prompt via un fichier | Lecture seule + garde-fous ; données jetables uniquement |
| Entrées malformées | Taille de demande limitée, JSON objet uniquement, nom d'outil vérifié |

**Limite connue :** le mot de passe Gradio circule en clair sans HTTPS ; hors machine locale, utiliser un reverse proxy HTTPS.

## 6. Lancer la démo (ordre conseillé)
1. `pytest -q` → 19 tests passent.
2. `python -m mayerfeld_mcp.client` → protocole brut, sans clé (démo la plus sûre).
3. `mayerfeld-mcp-ui` → http://127.0.0.1:7860, onglet 1 (outils), puis 2 (agent), puis 3 (sandbox).

## 7. Scénario de démo (≈3 min)
1. Onglet 1 : « Découvrir les outils » → 3 outils (lecture seule). Appeler `read_file` avec `{"path": "notes.txt"}`.
2. Onglet 2 : « Liste mes fichiers et résume taches.md » → montrer la **trace** : c'est le modèle qui choisit.
3. Montrer un refus : `{"path": "../pyproject.toml"}` → erreur du garde-fou.
4. Décocher « lecture seule », demander de créer `test.txt`, vérifier dans l'onglet 3.

## 8. Plan B
Captures d'écran ou courte vidéo de chaque étape ; le client en ligne de commande fonctionne sans réseau ni clé.

## 9. Statut des vérifications
Testé automatiquement (19 tests) et par script sur le serveur HTTP réel (Linux). **À vérifier manuellement** : appel Gemini depuis l'interface web et rendu dans le navigateur sous Windows.

## 10. Limites
stdio uniquement ; un sous-processus serveur par action ; pas de confirmation humaine par écriture (la lecture seule joue ce rôle) ; quotas et noms de modèles Gemini susceptibles de changer.
