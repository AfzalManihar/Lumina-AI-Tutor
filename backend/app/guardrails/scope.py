"""Scope guardrail: Lumina is a study tutor. Clearly non-study requests (recipes, entertainment picks, horoscopes,
betting, shopping...) get a short fixed warning and NO model call, so they cost zero tokens and cannot be answered.

Limits, stated plainly: this is a deterministic pattern list. It catches the obvious cases ("how to bake a cake") but a
cleverly worded or non-English request can slip past it. The tutor's system prompt carries the same rule as a second layer
(see agents/tutor.py), and neither layer is a complete defence."""
from __future__ import annotations

import re

_FOOD = (r"cakes?|cookies?|biryani|pizza|pasta|burgers?|noodles|brownies?|omelette|sandwich|maggi|paneer|dosa|samosa|roti|curry|"
         r"soup|smoothie|pancakes?|bread|chai|tea|coffee|dal|khana|dish|meal|dinner|lunch|breakfast|dessert|sweets?|halwa|kheer")
# category -> patterns. Every pattern is phrased as a REQUEST so study questions that merely mention a topic still pass
# ("chemistry of baking soda", "weather versus climate", "the 1929 stock market crash").
_CATEGORIES: dict[str, list[str]] = {
    "cooking": [
        r"\b(?:how (?:do i|to|can i|should i)|recipe (?:for|of)|ingredients? (?:for|of|to make)|steps? to|teach me to|show me how to)\b[^.?!]{0,40}\b(?:bake|cook|fry|grill|roast|brew)\b(?!\s+the\s+books)",
        rf"\b(?:bake|baking|make|making|prepare|cook|cooking)\b[^.?!]{{0,25}}\b(?:a |an |the |some )?(?:{_FOOD})\b",
        r"\brecipes?\b",
        rf"\b(?:{_FOOD})\b[^.?!]{{0,20}}\b(?:kaise|kese|kaisay|banane|banana|banao|banate|banaye|bana)\b",
        r"\b(?:khana|recipe|nuskha)\s+(?:batao|bataiye|bata do|sikhao)\b",
    ],
    "entertainment": [
        r"\b(?:recommend|suggest|best|top \d+|good)\b[^.?!]{0,25}\b(?:movies?|films?|web ?series|songs?|netflix|anime|games? to play)\b",
        r"\b(?:movies?|films?|web ?series|songs?|gaane|gaana|gana)\b[^.?!]{0,15}\b(?:batao|bataiye|suggest|recommend|sunao)\b",
        r"\b(?:lyrics (?:of|for|to)|box office|celebrity|bollywood gossip|gossip)\b",
        r"\b(?:tell me|say|give me|crack)\b[^.?!]{0,12}\b(?:a |one )?(?:joke|jokes|meme|riddle for fun|funny story)\b",
        r"\b(?:joke|jokes|chutkula|chutkule|meme)s?\s+(?:sunao|bolo|batao|suna)\b|\bsunao\b[^.?!]{0,10}\b(?:joke|chutkula|gaana)\b",
        r"\b(?:roast me|truth or dare|play a game with me|let'?s play)\b",
        r"\b(?:gta|pubg|free ?fire|fortnite|minecraft)\b[^.?!]{0,20}\b(?:cheat|code|tips|tricks|hack)\b",
    ],
    "sports": [
        r"\bwho (?:is going to|will|would|is gonna) win\b[^.?!]{0,30}\b(?:match|game|final|cup|series|league|ipl|trophy)\b",
        r"\b(?:match|game)\b[^.?!]{0,15}\b(?:kaun|kon|kisne)\b[^.?!]{0,12}\b(?:jeeta|jita|jeet|jeetega|haara)\b",
        r"\b(?:who won|who will win|score of|live score|match score|match result|points table)\b[^.?!]{0,40}\b(?:ipl|match|game|cricket|football|world cup|final|series|league)\b",
        r"\b(?:ipl|cricket|football)\b[^.?!]{0,15}\b(?:score|match|prediction|today|yesterday|tonight)\b",
        r"\b(?:ipl|cricket) (?:score|match)\b",
    ],
    "personal_creative": [
        r"\b(?:write|compose|make)\b[^.?!]{0,20}\b(?:love|romantic|birthday|anniversary|breakup|rap)\b[^.?!]{0,10}\b(?:poem|poetry|song|letter|message|shayari|wish|text)\b",
        r"\bshayari\b|\bpick-?up lines?\b",
        r"\b(?:horoscope|zodiac sign|astrology|kundli|love (?:advice|life)|girlfriend|boyfriend|dating|crush|propose|breakup|my ex)\b",
    ],
    "health_lifestyle": [
        r"\b(?:how (?:do i|to|can i)|tips? (?:to|for)|ways? to)\b[^.?!]{0,15}\b(?:lose weight|weight loss|gain weight|get abs|six pack|build muscle|get fair|grow hair)\b",
        r"\b(?:diet plan|gym routine|workout plan|skin ?care routine|home remedy|home remedies)\b",
    ],
    "money_shopping_travel": [
        r"\b(?:which|best|good)\b[^.?!]{0,15}\b(?:stocks?|crypto(?:currency)?|shares?|mutual funds?)\b[^.?!]{0,15}\b(?:to buy|to invest|should i buy)\b",
        r"\b(?:stock|share market|crypto|bitcoin|trading) (?:tips?|tip|prediction|price (?:today|now))\b|\bshould i (?:buy|invest in|sell)\b[^.?!]{0,20}\b(?:stocks?|shares?|bitcoin|crypto|gold)\b",
        r"\b(?:paise|money)\b[^.?!]{0,15}\b(?:kaise|how to)\b[^.?!]{0,10}\b(?:kamaye|kamao|kamane|earn|make)\b|\b(?:how to|ways to) (?:earn|make) (?:money|cash)\b",
        r"\b(?:bitcoin|crypto(?:currency)?|stocks?|shares?|gold|mutual funds?)\b[^.?!]{0,25}\b(?:good investment|worth (?:buying|investing)|safe to invest)\b",
        r"\b(?:restaurants?|cafes?|hotels?|salons?|gyms?)\b[^.?!]{0,12}\bnear (?:me|here)\b",
        r"\b(?:betting|casino|lottery|jackpot)\b",
        r"\b(?:best|which)\b[^.?!]{0,15}\b(?:phone|laptop|car|bike|hotel|restaurant)\b[^.?!]{0,15}\b(?:to buy|to book|near me|under)\b",
        r"\b(?:flight tickets?|book a (?:hotel|flight|cab)|places to visit|trip (?:to|plan)|tour plan)\b",
    ],
    "news_weather": [
        r"\b(?:what(?:'s| is) the weather(?:\s+(?:like|today|tomorrow|now|outside|in\b)|\s*[?!.]*$)|weather (?:today|tomorrow|now|forecast|in [a-z]+)|will it rain|temperature (?:today|now|in [a-z]+))",
        r"\b(?:mausam|barish)\b[^.?!]{0,15}\b(?:kaisa|kaise|aaj|kal|ka haal)\b",
        r"\b(?:latest news|today'?s news|breaking news|aaj ki khabar|news today)\b",
    ],
    "misuse": [
        r"\b(?:hack|crack|steal)\b[^.?!]{0,15}\b(?:instagram|whatsapp|facebook|wifi|wi-fi|account|password|snapchat)\b",
    ],
}
_COMPILED = {cat: [re.compile(p, re.I) for p in pats] for cat, pats in _CATEGORIES.items()}

REFUSAL = ("This looks outside what I can help with. I'm a study tutor, so I only answer learning questions: topics, your "
           "documents, lessons, quizzes and study plans. Try asking about a subject you're studying.")

INJECTION_REFUSAL = ("I can't follow instructions that try to change my rules or reveal my hidden instructions. "
                     "If you have a study question, ask it directly and I'll help.")


def scope_category(text: str) -> str | None:
    """Name of the first non-study category the request matches, or None."""
    for cat, pats in _COMPILED.items():
        if any(p.search(text) for p in pats):
            return cat
    return None


def is_off_topic(text: str, *, documents_selected: bool = False) -> bool:
    """True for clearly non-study requests. When the user has selected their own documents the question is answered
    only from those documents anyway, so the pattern check is skipped."""
    if documents_selected:
        return False
    return scope_category(text) is not None
