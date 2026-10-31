"""A small Freebase-style knowledge graph used by the lab.

Deliberately hand-sized: every triple is checkable by eye, which is the
point -- we want to *see* that constrained decoding can only walk real edges.
"""

TRIPLES = [
    # Edgar Allan Poe
    ("Edgar Allan Poe", "people.person.place_of_birth", "Boston"),
    ("Edgar Allan Poe", "people.person.place_of_death", "Baltimore"),
    ("Edgar Allan Poe", "people.person.nationality", "United States"),
    ("Edgar Allan Poe", "people.person.education", "University of Virginia"),
    ("Edgar Allan Poe", "people.person.notable_work", "The Raven"),
    # Martin Luther King, Jr.
    ("Martin Luther King, Jr.", "people.person.place_of_birth", "Atlanta"),
    ("Martin Luther King, Jr.", "people.person.place_of_death", "Memphis"),
    ("Martin Luther King, Jr.", "people.person.nationality", "United States"),
    ("Martin Luther King, Jr.", "people.person.education", "Morehouse College"),
    ("Martin Luther King, Jr.", "people.person.education", "Boston University"),
    ("Martin Luther King, Jr.", "people.person.award_received", "Nobel Peace Prize"),
    # Jamaica
    ("Jamaica", "location.country.languages_spoken", "Jamaican English"),
    ("Jamaica", "location.country.languages_spoken", "English language"),
    ("Jamaica", "location.country.currency_used", "Jamaican dollar"),
    # places
    ("Baltimore", "location.location.containedby", "United States"),
    ("Boston", "location.location.containedby", "United States"),
    ("Atlanta", "location.location.containedby", "United States"),
    ("Memphis", "location.location.containedby", "United States"),
    ("Washington, D.C.", "location.location.containedby", "United States"),
    ("United States", "location.country.languages_spoken", "English language"),
    ("Jamaican English", "location.location.containedby", "Jamaica"),
]

# Question -> (topic entity, gold path as [(entity, relation, entity), ...])
QUESTIONS = [
    {
        "id": "poe-birth",
        "question": "Where was Edgar Allan Poe born?",
        "topic": "Edgar Allan Poe",
        "gold": [("Edgar Allan Poe", "people.person.place_of_birth", "Boston")],
    },
    {
        "id": "mlk-school",
        "question": "Which colleges did Martin Luther King, Jr. attend?",
        "topic": "Martin Luther King, Jr.",
        "gold": [
            ("Martin Luther King, Jr.", "people.person.education", "Morehouse College"),
            ("Martin Luther King, Jr.", "people.person.education", "Boston University"),
        ],
    },
    {
        "id": "ja-lang",
        "question": "What languages are spoken in Jamaica?",
        "topic": "Jamaica",
        "gold": [
            ("Jamaica", "location.country.languages_spoken", "Jamaican English"),
            ("Jamaica", "location.country.languages_spoken", "English language"),
        ],
    },
    {
        "id": "balt-country",
        "question": "What country contains Baltimore, and what languages are spoken there?",
        "topic": "Baltimore",
        "gold": [
            ("Baltimore", "location.location.containedby", "United States"),
            ("United States", "location.country.languages_spoken", "English language"),
        ],
    },
]


class KB:
    def __init__(self, triples):
        self.out = {}
        self.relations = set()
        self.entities = set()
        for h, r, t in triples:
            self.out.setdefault(h, []).append((r, t))
            self.relations.add(r)
            self.entities.add(h)
            self.entities.add(t)

    def neighbors(self, entity):
        return self.out.get(entity, [])

    def has_edge(self, h, r, t):
        return (r, t) in self.out.get(h, [])

    def walk_paths(self, start, max_hops=2):
        """All simple paths starting at `start` up to `max_hops` edges."""
        paths = []

        def dfs(node, path, used):
            if path:
                paths.append(list(path))
            if len(path) >= max_hops:
                return
            for r, t in self.neighbors(node):
                if t in used:
                    continue
                path.append((node, r, t))
                used.add(t)
                dfs(t, path, used)
                used.remove(t)
                path.pop()

        dfs(start, [], {start})
        return paths


KB_DEFAULT = KB(TRIPLES)
