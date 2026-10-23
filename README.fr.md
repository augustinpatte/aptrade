# APtrade

**Une expérience : tester honnêtement des stratégies de trading et des portefeuilles face au S&P 500, avec une application web locale pour explorer les résultats et tester son propre portefeuille.** · [English version](README.md)

> **Démo en ligne :** _lien bientôt disponible_

APtrade prend des idées de trading, du day trading aux allocations sur plusieurs mois,
et les fait tourner sur de vraies données de marché (2016 à 2026), frais compris, avec
des règles strictes écrites à l'avance et le S&P 500 comme référence. L'application
montre toutes les approches côte à côte : rendements sur 3 ans et depuis 2017, pires
baisses, volatilité, risque par position, points forts et points faibles.

Le projet est né de l'audit d'un repo GitHub populaire de day trading, puis il est
devenu un outil de test complet.

## Résultats

Tous les chiffres ci-dessous sont calculés par le code à partir de vraies données
Alpaca, frais compris, et réécrits automatiquement par `aptrade export`.

<!-- results:start -->
_Lance `aptrade export` pour remplir ce tableau avec tes données._
<!-- results:end -->

## Les approches

**Allocation diversifiée (le curseur).** Tu choisis ta part d'actions américaines (SPY) ;
le reste va dans 15 ETF (obligations, or, matières premières, international, immobilier)
pondérés par l'inverse de leur volatilité, rééquilibrés chaque mois.
- ▲ L'approche la plus simple, des frais très faibles ; à 50 % de SPY, elle a réduit la pire baisse d'environ un tiers.
- ▲ A tenu aussi bien que les stratégies à signal, avec trois fois moins de transactions.
- ▼ Moins de rendement que le SPY en marché haussier, à peu près en proportion de la part hors actions.
- **Risque par position :** 16 ETF, la plus grosse ligne est le SPY à la part choisie, sans levier.

**Suivi de tendance.** 15 ETF diversifiés, chacun gardé tant que son rendement sur 3 mois
est positif, pondérés par l'inverse de leur volatilité, le reste en bons du Trésor.
- ▲ Les plus petites baisses (baisse max d'environ 8 à 12 % contre 34 % pour le SPY).
- ▲ Rendement ajusté du risque proche du SPY ; se met à l'écart dans les longs marchés baissiers.
- ▼ Rendement bien plus faible en marché haussier ; souvent à moitié en cash.
- **Risque par position :** jusqu'à 15 lignes, aucune dominante ; volatilité faible.

**Moitié S&P 500, moitié suivi de tendance.** Le moteur du marché avec un amortisseur.
- ▲ Environ deux tiers du rendement du SPY pour environ 60 % de sa pire baisse ; très stable.
- ▼ Trois fois plus de transactions que l'allocation simple pour un résultat proche.
- **Risque par position :** moitié en SPY en permanence, moitié sur jusqu'à 15 ETF ou en bons du Trésor.

**Rotation par momentum.** Chaque mois, les 3 ETF au meilleur rendement sur 12 mois, un tiers chacun.
- ▲ Le meilleur résultat de toutes les approches sur la période réservée de mai 2024 à oct. 2026 (+69 % contre +53 % pour le SPY) ; capte les grands mouvements d'une classe d'actifs.
- ▼ Concentrée, avec des baisses plus fortes que le SPY ; faible sur les années précédentes.
- **Risque par position :** trois lignes de 33 % ; l'approche la plus concentrée.

**Acheter le repli (3 à 10 jours).** Acheter un ETF d'indice ou de secteur en tendance
haussière après une forte baisse de 2 jours, revendre au rebond.
- ▲ Baisse max faible, souvent en cash, règles claires et mécaniques.
- ▼ Beaucoup de transactions : 1 à 3 % de frais par an pèsent sur le résultat.
- **Risque par position :** au plus 5 positions de 20 %, gardées 1 à 10 jours.

**Cassure du range d'ouverture (day trading).** La stratégie du repo d'origine, sur des bougies de 5 minutes.
- ▲ Contrôle du risque strict : 0,25 % du compte par trade, limite de perte de 1 % par jour, tout fermé chaque soir.
- ▼ En intraday, les frais mangent 15 à 20 % du mouvement typique ; il faut être devant l'écran pendant la séance.
- **Risque par position :** 0,25 % du compte, 2 positions au plus.

Le détail, l'objectif et le résultat de chaque approche sont dans la page **Stratégies**
de l'app et dans [PREREGISTRATION.md](PREREGISTRATION.md).

## Ce que l'expérience a montré

- Une allocation diversifiée fixe a gardé environ deux tiers du rendement du S&P 500 pour
  environ deux tiers de sa pire baisse, sans aucun signal de trading.
- Sur plusieurs jours ou semaines, les frais deviennent faibles ; en intraday, ils dominent.
- Les signaux de timing ont changé la forme du risque plus que le rendement.
- Le S&P 500 lui-même est resté la référence la plus dure à battre en rendement ajusté du risque.

## Garde-fous

| Garde-fou | Ce qu'il fait |
|---|---|
| Règles écrites avant les données | Chaque approche, ses paramètres et son objectif ont été versionnés dans [PREREGISTRATION.md](PREREGISTRATION.md) avant le téléchargement des données. Aucun réglage après coup. |
| Une période de test réservée | Les 25 % de jours les plus récents sont mis de côté, jamais utilisés pour choisir, et chaque consultation est comptée. |
| Walk-forward | Quand des paramètres sont comparés, le gagnant est choisi sur le passé et noté sur des données qu'il n'a jamais vues. |
| Trading réaliste | Signaux sur les clôtures, ordres à l'ouverture suivante, 3 points de base par côté sur chaque dollar échangé, gap au-delà d'un stop exécuté au prix du gap. |
| Ni levier, ni vente à découvert | Au plus 100 % investi ; le reste en bons du Trésor à 1-3 mois (BIL). |
| Limites de risque en dur (intraday) | Au plus 1 % du capital risqué par trade, 3 % de perte par jour, 5 positions, 10 trades par jour, écrits dans le code. |
| Statistiques honnêtes | Intervalles de confiance par bootstrap par blocs ; la barre monte à chaque idée supplémentaire testée. |
| Aucun regard sur le futur | Un test détruit tous les prix après une date et vérifie qu'aucune décision antérieure ne change. |
| Tes clés restent à toi | Les clés sont dans `.env` sur ta machine, ignoré par git ; `./check_secrets.sh` bloque un push qui les publierait. |

## L'utiliser toi-même : tutoriel pas à pas

### 1. Installer (5 minutes)

Il faut Python 3.10 ou plus : vérifie avec `python3 --version`. Sur Mac, si la version est
plus ancienne, installe la dernière version depuis [python.org](https://www.python.org/downloads/).

**macOS / Linux**

```bash
git clone https://github.com/augustinpatte/aptrade.git
cd aptrade
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

**Windows (PowerShell)**

```powershell
git clone https://github.com/augustinpatte/aptrade.git
cd aptrade
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e .
```

### 2. Ouvrir l'app

```bash
aptrade app
```

Ton navigateur s'ouvre sur le tableau de bord. Les pages **Tableau de bord**,
**Allocation**, **Stratégies** et **Méthode** marchent tout de suite, à partir des
résultats inclus dans le repo.

### 3. Obtenir tes propres clés Alpaca gratuites (pour « Mon portefeuille » et les données fraîches)

1. Crée un compte gratuit sur [alpaca.markets](https://alpaca.markets) (un email suffit
   pour un compte paper, sans dépôt).
2. Dans le tableau de bord, passe en **Paper Trading**, puis génère une **clé API**.
   Copie la clé et le secret : le secret ne s'affiche qu'une fois.
3. Donne-les à APtrade, au choix :
   - dans l'app : page **Réglages**, colle les deux, **Enregistrer** ;
   - ou dans le terminal :

```bash
cp .env.example .env
# puis ouvre .env dans un éditeur de texte et remplis :
# ALPACA_API_KEY=ta_cle_ici
# ALPACA_SECRET_KEY=ton_secret_ici
```

Les clés sont enregistrées uniquement dans `.env` sur ta machine. Ne les colle jamais
dans un chat, une issue ou un site public. Lire des données ne passe jamais
d'ordre ; les ordres ne viennent que de `aptrade live execute` ou `aptrade live run`.

### 4. Télécharger des données fraîches et tout recalculer

```bash
aptrade swing fetch      # données journalières des 26 ETF depuis 2016 (une minute)
aptrade export           # recalcule les résultats, l'app et les tableaux de ce README
aptrade app
```

Ou clique sur **Mettre à jour** dans la page **Réglages**.

### 5. Tester ton propre portefeuille

Dans l'app, **Mon portefeuille** : choisis des ETF (ou tape n'importe quel ticker), fixe
les poids (100 % au plus ; le reste est gardé en cash), choisis la fréquence de
rééquilibrage, puis **Tester**. Tu obtiens les mêmes KPI, graphiques et comparaison avec
le SPY que la recherche.

### Les fois suivantes

```bash
cd aptrade
source .venv/bin/activate      # Windows : .venv\Scripts\Activate.ps1
aptrade app
```

### En cas de problème

- `command not found: aptrade` : l'environnement virtuel n'est pas actif ; relance la
  ligne `source .venv/bin/activate`.
- Sur Mac, `python3` demande d'accepter une licence Xcode : installe Python depuis
  python.org au lieu d'utiliser celui d'Apple.
- `ALPACA_API_KEY and ALPACA_SECRET_KEY are not set` : étape 3.
- `subscription does not permit querying recent SIP data` : APtrade passe tout seul sur le
  flux gratuit IEX et te le signale ; les résultats sont alors un peu moins précis.

## L'utiliser avec un agent IA (Claude Code, Codex, Grok)

APtrade fournit 11 skills au format ouvert Agent Skills (`skills/*/SKILL.md`), lus par
Claude Code, OpenAI Codex, Grok Build et d'autres agents :

| Skill | Ce que l'agent en fait |
|---|---|
| `aptrade-research` | Teste n'importe quel portefeuille ou stratégie face au SPY, 3 dernières années et depuis 2016 |
| `aptrade-allocate` | Demande ton montant, ton horizon et ton seuil de douleur, montre des options avec leur historique, enregistre ta cible |
| `aptrade-rebalance` | Compare ton compte avec la cible et prépare les ordres |
| `aptrade-budget` | Dimensionne chaque ligne selon ton montant : dollars, actions, cash restant |
| `aptrade-risk` | Vérifie chaque plan face aux limites en dur ; arrêt d'urgence |
| `aptrade-broker` | Connecte Alpaca et exécute : seul en paper, avec ton code en réel |
| `aptrade-alerts` | Écarts, baisse depuis le sommet, rééquilibrage à faire |
| `aptrade-news` | Actualités et dépôts officiels sur tes lignes, avec sources |
| `aptrade-analyst` | Résultats d'entreprises depuis la SEC, frais et contenu des ETF |
| `aptrade-congress` | Transactions déclarées par les élus du Congrès, avec le délai de 45 jours |
| `aptrade-daytrade` | L'expérience de day trading, en mode recherche uniquement |

**Installer.** Dans le repo, les skills sont déjà visibles (`.claude/skills` et
`.agents/skills`). Pour les avoir dans tous tes projets :

```bash
./install_skills.sh                                   # les relie dans ~/.claude, ~/.agents et ~/.grok
```

Claude Code peut aussi les installer comme plugin :

```
/plugin marketplace add augustinpatte/aptrade
/plugin install aptrade@aptrade
```

Ensuite, il suffit de demander : *« Construis-moi un portefeuille avec au plus 20 % de baisse, 2 000 $, et rééquilibre mon compte paper. »*

## Gérer un vrai portefeuille

L'agent (ou toi, depuis le terminal) peut faire toute la boucle :

```bash
aptrade target set --weights SPY=60,IEF=30,GLD=10 --rebalance M --max-capital 2000
aptrade live run               # paper : plan + contrôles de risque + ordres, en une commande
aptrade live alerts            # écarts, baisse, rééquilibrage à faire
```

`aptrade live run` ne fait rien quand chaque ligne est dans sa marge : on peut le lancer
tous les jours ou laisser un agent le lancer à intervalle régulier. Pour relire avant
d'envoyer, coupe en deux : `aptrade live plan` puis `aptrade live execute <plan_id>`.

Pour de l'argent réel, ajoute tes clés live dans `.env` (`ALPACA_LIVE_API_KEY`,
`ALPACA_LIVE_SECRET_KEY`) et mets `APTRADE_ALLOW_LIVE=1`. Ensuite :

```bash
aptrade live run --live                 # C'EST TOI qui le lances : il affiche les ordres puis un code à retaper
```

Ou en deux temps : un agent prépare `aptrade live plan --live` et l'explique, puis tu
lances `aptrade live execute <plan_id> --live`. Dans tous les cas, les ordres réels ne
partent qu'après ton code. En pratique : l'agent surveille (`aptrade live alerts`), te
prévient quand un rééquilibrage est dû, et tu valides en 30 secondes, environ une fois par mois.

**Comment ton argent est protégé**

- Seuls les symboles de ta cible sont échangés ; le reste du compte n'est jamais touché.
- `--max-capital` plafonne ce qu'APtrade gère. Commence petit.
- Limites en dur dans le code : ni levier ni vente à découvert, uniquement pendant la
  séance, plans valables 15 minutes, au plus 30 ordres par plan et 2 plans réels par jour,
  arrêt d'urgence (`aptrade live kill`).
- Paper et réel utilisent des clés différentes ; une clé paper ne peut jamais passer un
  ordre réel.
- Un plan réel demande un code à 6 chiffres affiché uniquement dans ton terminal. Un agent
  lit la sortie de ses commandes, pas ton terminal : il peut préparer un plan réel, pas
  l'approuver.
- Chaque ordre a un identifiant unique : une relance après un plantage ne l'envoie
  jamais deux fois.

**Ce que ça ne protège pas.** Un agent qui a un accès complet à ton ordinateur peut lire
`.env`. Le code bloque un agent qui suit ses instructions ou qui se trompe ; il ne bloque
pas un agent qui les ignorerait délibérément pour appeler le courtier lui-même. Garde ton
agent en mode « demander avant d'exécuter une commande » sur la machine qui contient les
clés réelles, et ne laisse pas de clés réelles sur une machine où des agents tournent
sans surveillance.

## Sources de données

Les prix pour la recherche viennent d'une de ces trois sources, choisie avec
`APTRADE_DATA` dans `.env` :

| Source | Clé | Couverture | Limite |
|---|---|---|---|
| `alpaca` | tes clés Alpaca | actions et ETF US | gratuit avec un compte paper |
| `tiingo` | clé gratuite (tiingo.com) | actions et ETF US | API officielle, quotas sur l'offre gratuite |
| `yahoo` | aucune | US et international | non officiel : peut changer ou limiter sans prévenir, usage personnel |

`auto` (par défaut) prend Alpaca si ses clés sont là, sinon Tiingo si sa clé est là,
sinon Yahoo. Quelqu'un sans aucune clé peut donc quand même tester des portefeuilles.
Chaque source a son propre cache dans `data/cache/<source>/`, et les prix sont ajustés
des splits et dividendes.

Les ordres passent uniquement par Alpaca (comptes US). Interactive Brokers et
Trading 212 ont été étudiés puis écartés : un adaptateur n'est publié qu'après avoir
tourné sur un vrai compte paper. L'interface courtier est dans
`aptrade/brokers/base.py` si tu veux en ajouter un.

## Ligne de commande

```bash
aptrade app                                   # l'application web
aptrade swing fetch                           # données journalières des 26 ETF
aptrade export                                # recalcule results/results.json et les tableaux du README
aptrade swing backtest --strategy trend       # une stratégie face au SPY (trend, meanrev, blend, static, rotation)
aptrade swing sweep --strategy trend          # walk-forward sur ses paramètres pré-enregistrés
aptrade swing holdout --strategy blend        # un regard sur la période réservée, enregistré
aptrade intraday backtest                     # le test de day trading sur bougies de 5 minutes
aptrade runs                                  # tous les runs, depuis le journal SQLite local
aptrade test-portfolio --weights SPY=60,IEF=40   # n'importe quels poids face au SPY (--json pour les agents)
aptrade target set|show                       # le portefeuille qu'APtrade maintient
aptrade live status|plan|execute|alerts|kill  # un compte Alpaca paper ou réel
```

## Publier ta propre démo

[Streamlit Community Cloud](https://streamlit.io/cloud) héberge l'app gratuitement depuis GitHub :

1. `aptrade export`, puis versionne `results/results.json` et le README.
2. Sur share.streamlit.io : **New app**, choisis ton repo, fichier principal `app/Home.py`.
3. Dans **Settings > Secrets** de l'app, ajoute `APTRADE_PUBLIC_DEMO = "1"`. Dans ce mode,
   l'app ne demande jamais de clés et ne télécharge rien : un visiteur ne doit pas saisir
   ses clés sur un site public.

## Données et licences

Les prix viennent d'Alpaca avec ta propre clé et restent sur ta machine (`data/`, ignoré
par git). Les accords de données de marché interdisent en général de redistribuer les
données brutes : le repo ne publie donc que des rendements mensuels et des statistiques
(`results/results.json`). Seule exception : une petite fixture de test sur TSLA reprise
du repo d'origine sous licence MIT (`tests/fixtures/NOTICE.md`).

## Limites connues

- Dix ans, c'est une seule histoire de marché ; l'avenir peut être différent.
- La période réservée couvre environ 2,4 ans : assez pour rejeter une idée, pas pour en prouver une.
- Les simulations utilisent des actions fractionnées et un coût fixe par côté, sans impôts.
- Les 15 ETF diversifiés ont été choisis en 2026 ; ils existaient tous en 2016, mais les
  choisir reste une décision prise avec le recul.
- L'exécution des ordres a tourné sur un compte paper Alpaca. Le chemin argent réel (`--live`)
  est le même code plus le code de confirmation, mais il n'a pas encore tourné avec de
  l'argent réel : commence avec un petit `--max-capital`.
- Les prix Yahoo viennent d'une adresse non officielle qui peut changer sans prévenir.

## Organisation du projet

```
aptrade/
├── app/                 l'application web (Streamlit), anglais et français
├── aptrade/
│   ├── swing/           moteur journalier, stratégies, mesures face au SPY, walk-forward, portefeuilles perso
│   ├── live/            compte réel ou paper : cible, plan, limites de risque, exécution, alertes
│   ├── brokers/         interface courtier et adaptateur Alpaca
│   ├── sources.py       prix journaliers Yahoo et Tiingo
│   ├── intraday/        la recherche en day trading (bougies de 5 minutes)
│   ├── data.py          données Alpaca avec cache local
│   ├── store.py         journal SQLite des runs
│   ├── export.py        résultats pour l'app, sans prix
│   └── cli.py           la commande aptrade
├── results/             research.json (approches) et results.json (données de l'app)
├── skills/              les 11 skills pour agents (aussi reliés depuis .claude/skills et .agents/skills)
├── research/            le journal de recherche et les scripts de chaque étape
├── tests/               tests hors ligne (python -m unittest discover -s tests -t .)
├── PREREGISTRATION.md   les règles, écrites avant les données
└── check_secrets.sh     à lancer avant chaque push
```

## Pas un conseil financier

APtrade est un logiciel éducatif et une expérience. Il fait de l'arithmétique sur des
données de marché historiques ; il ne voit pas l'avenir, et les performances passées ne
préjugent pas des performances futures. Il ne passe des ordres que sur le compte que tu connectes, dans les limites ci-dessus, et les ordres réels seulement après que tu as tapé un code de confirmation.

Licence MIT · Augustin Patte · Né de l'audit de
[day-trader-skill](https://github.com/Jakeschincariol/day-trader-skill) (MIT).
