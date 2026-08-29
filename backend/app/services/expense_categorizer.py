"""Two-level expense categorization.

Every debit is mapped to a ``(primary, subcategory, source)`` triple. ``primary``
is one of the keys in :data:`TAXONOMY`; ``subcategory`` is one of its members.

The taxonomy is grounded in Plaid's Personal Finance Category standard
(https://plaid.com/documents/transactions-personal-finance-category-taxonomy.csv)
but tailored to how a personal-CFO user budgets.

Three primaries are *non-spending* (money movement, not consumption): credit-card
payments, transfers, and investments. They are excluded from spending totals via
:data:`NON_SPENDING` / :func:`is_spending` so the summary doesn't double-count a
credit-card payment against the card's own imported transactions.

Rules run first (free, deterministic). Anything the rules can't place comes back
as ``("other", "other", "fallback")`` and is handed to the AI categorizer for the
long tail of local merchants — see ``ai_categorizer.py``.
"""

import re

# ─── Taxonomy ────────────────────────────────────────────────────────────────
# primary -> ordered list of subcategory keys. The last entry of each list is the
# catch-all subcategory used when the primary is known but the sub isn't.

TAXONOMY: dict[str, list[str]] = {
    # Spending
    "housing": ["rent", "hoa_fees", "home_improvement", "home_services", "furnishings", "other"],
    "utilities": ["electric_gas", "water_sewage_trash", "internet_cable", "phone", "other"],
    "food_and_drink": ["groceries", "restaurant", "fast_food", "coffee", "alcohol", "other"],
    "transportation": ["gas", "auto_service", "auto_parts", "parking_tolls", "public_transit", "rideshare", "registration", "other"],
    "travel": ["flights", "lodging", "rental_car", "other"],
    "shopping": ["clothing", "electronics", "home_goods", "online_marketplace", "department_store", "sporting_goods", "general_merchandise", "other"],
    "entertainment": ["movies_tv", "events", "video_games", "gambling", "hobbies", "other"],
    "subscriptions": ["streaming", "software", "news", "memberships", "other"],
    "health": ["doctor", "dental", "vision", "pharmacy", "mental_health", "fitness", "other"],
    "personal_care": ["hair_beauty", "spa_massage", "laundry", "other"],
    "insurance": ["auto", "home", "health", "life", "other"],
    "debt_payments": ["mortgage", "auto_loan", "student_loan", "personal_loan", "other_loan"],
    "education": ["tuition", "childcare", "supplies", "other"],
    "pets": ["vet", "pet_supplies", "other"],
    "financial": ["bank_fees", "interest_charge", "professional_services", "other"],
    "taxes": ["income_tax", "property_tax", "vehicle_licensing", "gov_fees", "other"],
    "gifts_donations": ["charity", "gifts", "other"],
    "cash": ["atm_withdrawal", "other"],
    "other": ["other"],
    # Non-spending (money movement)
    "credit_card_payment": ["credit_card_payment"],
    "transfer": ["internal", "external", "p2p", "other"],
    "investment": ["brokerage", "retirement", "other"],
}

# Primaries that represent money movement, not consumption. Excluded from spend.
NON_SPENDING: frozenset[str] = frozenset({"credit_card_payment", "transfer", "investment"})

PRIMARY_DISPLAY: dict[str, str] = {
    "housing": "Housing",
    "utilities": "Utilities",
    "food_and_drink": "Food & Drink",
    "transportation": "Transportation",
    "travel": "Travel",
    "shopping": "Shopping",
    "entertainment": "Entertainment",
    "subscriptions": "Subscriptions",
    "health": "Health & Medical",
    "personal_care": "Personal Care",
    "insurance": "Insurance",
    "debt_payments": "Loans & Debt",
    "education": "Education & Childcare",
    "pets": "Pets",
    "financial": "Fees & Financial",
    "taxes": "Taxes & Government",
    "gifts_donations": "Gifts & Donations",
    "cash": "Cash & ATM",
    "other": "Other",
    "credit_card_payment": "Credit Card Payment",
    "transfer": "Transfers",
    "investment": "Investments & Savings",
}

SUBCATEGORY_DISPLAY: dict[str, str] = {
    "rent": "Rent",
    "hoa_fees": "HOA & Property Fees",
    "home_improvement": "Home Improvement",
    "home_services": "Home Services",
    "furnishings": "Furnishings",
    "electric_gas": "Electric & Gas",
    "water_sewage_trash": "Water, Sewer & Trash",
    "internet_cable": "Internet & Cable",
    "phone": "Phone",
    "groceries": "Groceries",
    "restaurant": "Restaurants",
    "fast_food": "Fast Food",
    "coffee": "Coffee Shops",
    "alcohol": "Beer, Wine & Liquor",
    "gas": "Gas & Fuel",
    "auto_service": "Auto Service & Repair",
    "auto_parts": "Auto Parts",
    "parking_tolls": "Parking & Tolls",
    "public_transit": "Public Transit",
    "rideshare": "Rideshare & Taxi",
    "registration": "Registration & Licensing",
    "flights": "Flights",
    "lodging": "Lodging",
    "rental_car": "Rental Cars",
    "clothing": "Clothing & Accessories",
    "electronics": "Electronics",
    "home_goods": "Home Goods",
    "online_marketplace": "Online Marketplaces",
    "department_store": "Department Stores",
    "sporting_goods": "Sporting Goods",
    "general_merchandise": "General Merchandise",
    "movies_tv": "Movies & TV",
    "events": "Events & Tickets",
    "video_games": "Video Games",
    "gambling": "Casinos & Gambling",
    "hobbies": "Hobbies & Recreation",
    "streaming": "Streaming",
    "software": "Software & Apps",
    "news": "News & Magazines",
    "memberships": "Memberships",
    "doctor": "Doctor & Medical",
    "dental": "Dental",
    "vision": "Vision",
    "pharmacy": "Pharmacy",
    "mental_health": "Mental Health",
    "fitness": "Fitness & Gym",
    "hair_beauty": "Hair & Beauty",
    "spa_massage": "Spa & Massage",
    "laundry": "Laundry & Dry Cleaning",
    "auto": "Auto Insurance",
    "home": "Home Insurance",
    "health": "Health Insurance",
    "life": "Life Insurance",
    "mortgage": "Mortgage",
    "auto_loan": "Auto Loan",
    "student_loan": "Student Loan",
    "personal_loan": "Personal Loan",
    "other_loan": "Loan Payment",
    "tuition": "Tuition",
    "childcare": "Childcare",
    "supplies": "School Supplies",
    "vet": "Veterinary",
    "pet_supplies": "Pet Supplies",
    "bank_fees": "Bank Fees",
    "interest_charge": "Interest Charges",
    "professional_services": "Professional Services",
    "income_tax": "Income Tax",
    "property_tax": "Property Tax",
    "vehicle_licensing": "Vehicle Licensing",
    "gov_fees": "Government Fees",
    "charity": "Charity & Donations",
    "gifts": "Gifts",
    "atm_withdrawal": "ATM & Cash",
    "credit_card_payment": "Credit Card Payment",
    "internal": "Internal Transfer",
    "external": "External Transfer",
    "p2p": "Person-to-Person",
    "brokerage": "Brokerage",
    "retirement": "Retirement",
    "other": "Other",
}

# Backward-compatible alias — insight_engine.py imports CATEGORY_DISPLAY.
CATEGORY_DISPLAY = PRIMARY_DISPLAY


def is_spending(primary: str) -> bool:
    """True if a primary category represents consumption (counts as an expense)."""
    return primary not in NON_SPENDING


def primary_display(primary: str) -> str:
    return PRIMARY_DISPLAY.get(primary, primary.replace("_", " ").title())


def subcategory_display(subcategory: str) -> str:
    return SUBCATEGORY_DISPLAY.get(subcategory, subcategory.replace("_", " ").title())


# ─── Rules ───────────────────────────────────────────────────────────────────
# Ordered (primary, subcategory, [patterns]); FIRST match wins. Non-spending
# detection comes first so credit-card payments and transfers are never mistaken
# for the merchants named inside their descriptions.

_RULES: list[tuple[str, str, list[str]]] = [
    # ── Non-spending: credit-card payments ──
    ("credit_card_payment", "credit_card_payment", [
        r"payment\s+to\s+.*\bcard\b", r"\bcard\b.*\bpayment\b",
        r"amex\s*epayment", r"american\s*express\s*ach\s*pmt",
        r"chase\s*credit\s*crd", r"citi\s*(card|autopay)", r"capital\s*one.*(pymt|pmt|payment|crd)",
        r"discover.*\b(e[- ]?pymt|payment)\b", r"\bcardmember\s*serv",
        r"\bautopay\b.*\bcard\b", r"bill\s*pay.*\bcard\s*ending",
        r"card\s*ending\s*in\s*\d+",
        # Bank of America prints "BANK OF AMERICA CREDITCARD ..." (no space before
        # 'card', so \bcard\b never matched); also match a bare "creditcard" token.
        r"bank\s*of\s*america.*credit\s*?card", r"\bcreditcard\b",
    ]),
    # ── Non-spending: transfers ──
    ("transfer", "p2p", [
        r"paypal\s*(instant\s*)?transfer", r"\bzelle\b", r"venmo", r"cash\s*app", r"square\s*cash",
    ]),
    ("transfer", "internal", [
        r"online\s*transfer", r"\btransfer\s*to\b", r"\bto\s*savings\b", r"from\s*checking",
        r"ext\s*trnsf", r"\bp2p\b", r"jpmorgan\s*chase\s*ext",
    ]),
    ("transfer", "external", [
        r"\bwire\s*(transfer|trans|out)\b", r"\bach\s*transfer\b", r"\bexternal\s*transfer\b",
    ]),
    # ── Non-spending: investments / savings ──
    ("investment", "brokerage", [
        r"\bvanguard\b", r"\bfidelity\b", r"charles\s*schwab", r"\bschwab\b", r"\betrade\b",
        r"\btd\s*ameritrade\b", r"\brobinhood\b", r"\bcoinbase\b", r"\bbrokerage\b",
        r"\bbetterment\b", r"\bwealthfront\b", r"\backorns\b",
    ]),
    ("investment", "retirement", [
        r"\b401k\b", r"\broth\s*ira\b", r"\bira\s*contrib", r"retirement\s*contrib",
    ]),

    # ── Cash / ATM ──
    ("cash", "atm_withdrawal", [
        r"atm\s*(withdrawal|cash|debit)", r"\bcash\s*withdrawal\b", r"withdrawal.*\batm\b",
    ]),

    # ── Debt: mortgage & loans ──
    ("debt_payments", "mortgage", [
        r"\bmortgage\b", r"\bmr\.?\s*cooper\b", r"\bnationstar\b", r"\bnsm\b.*cooper",
        r"\bloandepot\b", r"quicken\s*loans", r"rocket\s*mortgage", r"\bwells\s*fargo\s*home\s*mtg",
        r"\bchase\s*home\b", r"\bcaliber\s*home\b", r"\bcarrington\s*mtg", r"\bfreedom\s*mtg",
    ]),
    ("debt_payments", "auto_loan", [
        r"bmw\s*(bank|financial|fs)", r"bmwfs", r"toyota\s*financial", r"\btfs\b",
        r"honda\s*financial", r"ford\s*credit", r"gm\s*financial", r"ally\s*auto",
        r"chrysler\s*capital", r"nissan\s*(motor|financial)", r"\bcap(ital)?\s*one\s*auto",
        r"auto\s*loan", r"vehicle\s*loan",
    ]),
    ("debt_payments", "student_loan", [
        r"student\s*loan", r"\bnelnet\b", r"\bsallie\s*mae\b", r"\bnavient\b",
        r"\bmohela\b", r"great\s*lakes.*(loan|servic)", r"\bfedloan\b", r"\baidvantage\b",
    ]),
    ("debt_payments", "other_loan", [
        r"loan\s*paym", r"loan\s*pmt", r"\bloan\s*payt\b", r"\bloanpmt\b",
        r"sofi\b", r"lending\s*club", r"\bupstart\b", r"personal\s*loan",
        r"emp\s*cr\s*u.*loan", r"credit\s*union.*loan", r"\bcu\b.*loan\s*pay",
    ]),

    # ── Insurance ──
    ("insurance", "auto", [
        r"geico", r"progressive\s*(ins|gj|adv)", r"\ballstate\b", r"state\s*farm",
        r"\bliberty\s*mutual\b", r"\bnationwide\s*ins", r"\bfarmers\s*ins",
        r"\bamerican\s*family\b", r"\busaa\b", r"\bmercury\s*ins", r"\bthe\s*general\b",
        r"\bgeico\b", r"auto\s*insurance",
    ]),
    ("insurance", "health", [
        r"health\s*insurance", r"\baetna\b", r"\bcigna\b", r"\bhumana\b",
        r"united\s*health", r"\banthem\b", r"\bkaiser\b.*premium",
    ]),
    ("insurance", "life", [
        r"life\s*insurance", r"\bnorthwestern\s*mutual\b", r"\bmetlife\b", r"\bprudential\b",
        r"\bnew\s*york\s*life\b", r"\bguardian\s*life\b",
    ]),
    ("insurance", "home", [
        r"home(owner)?'?s?\s*insurance", r"renter'?s\s*insurance", r"\blemonade\s*ins",
    ]),
    ("insurance", "other", [r"\binsurance\b", r"\bins\s*prem", r"webpayment.*\bins\b"]),

    # ── Utilities ──
    ("utilities", "electric_gas", [
        r"pg&?e\b", r"pacific\s*gas", r"con\s*ed(ison)?", r"pse&?g", r"\bpuget\s*sound\s*ener",
        r"\bduke\s*energy\b", r"\bdominion\s*energy\b", r"\bsouthern\s*calif\s*edison\b",
        r"\bsce\b", r"\bxcel\s*energy\b", r"\bnational\s*grid\b", r"\bfpl\b", r"\bflorida\s*power\b",
        r"\bgeorgia\s*power\b", r"\bseattle\s*city\s*light\b", r"\bavista\b",
        r"\belectric\b", r"\benergy\b.*\b(bill|pay|util)", r"gas\s*co(mpany|\.)",
    ]),
    ("utilities", "water_sewage_trash", [
        r"water\s*(and\s*)?(sewer|wastewater|district|authority|service|company|util)",
        r"\bwastewater\b", r"\bsewer\b", r"\bwaste\s*management\b", r"\brepublic\s*services\b",
        r"\bwm\b.*waste", r"\btrash\b", r"\bgarbage\b", r"\brecology\b",
    ]),
    ("utilities", "internet_cable", [
        r"comcast", r"xfinity", r"spectrum\b", r"cox\s*comm", r"centurylink",
        r"\bwave\s*broadband\b", r"\bziply\b", r"\bfrontier\s*comm",
        r"internet\s*(service|provider|bill)", r"cable\s*(tv|bill|service)",
    ]),
    ("utilities", "phone", [
        r"\bat&?t\b", r"verizon", r"t.mobile", r"metro\s*pcs", r"\bsprint\b",
        r"\bmint\s*mobile\b", r"\bgoogle\s*fi\b", r"\bcricket\s*wireless\b", r"\bvisible\b",
    ]),

    # ── Housing ──
    ("housing", "hoa_fees", [r"\bhoa\b", r"hoadues", r"homeowner.*assoc", r"\bcondo\s*assoc"]),
    ("housing", "rent", [r"\brent\b(?!\s*a\s*car)", r"\bapartment", r"\bproperty\s*mgmt", r"\bleasing\b"]),
    ("housing", "home_improvement", [
        r"home\s*depot", r"lowe'?s\b", r"ace\s*hardware", r"true\s*value", r"\bmenards\b",
        r"\bharbor\s*freight\b", r"\bsherwin.williams\b",
    ]),
    ("housing", "furnishings", [
        r"wayfair", r"ikea\b", r"\bashley\s*furniture\b", r"\bpottery\s*barn\b",
        r"\bcrate\s*&?\s*barrel\b", r"\bwest\s*elm\b", r"\brestoration\s*hardware\b", r"furniture",
    ]),
    ("housing", "home_services", [
        r"plumber", r"electrician", r"\bhvac\b", r"pest\s*control", r"landscap", r"\bgardener\b",
        r"\bhandyman\b", r"\bcleaning\s*service\b", r"\bmerry\s*maids\b",
    ]),

    # ── Food & drink ──
    ("food_and_drink", "groceries", [
        r"whole\s*foods", r"trader\s*joe", r"safeway", r"kroger", r"publix", r"sprouts",
        r"aldi\b", r"wegmans", r"ralph'?s", r"vons\b", r"\bgiant\b", r"stop\s*&\s*shop",
        r"harris\s*teeter", r"fresh\s*(market|thyme|direct)", r"market\s*basket",
        r"grocery\s*outlet", r"winco\b", r"costco", r"sam'?s\s*club", r"\bqfc\b", r"\bfred\s*meyer\b",
        r"\bh\s*mart\b", r"\b99\s*ranch\b", r"grocery", r"supermarket",
    ]),
    ("food_and_drink", "coffee", [
        r"starbucks", r"\bsbux\b", r"dunkin", r"peet'?s\s*coffee", r"\bcaribou\s*coffee\b",
        r"\bphilz\b", r"\bblue\s*bottle\b", r"\bcoffee\b", r"\bcafe\b", r"\bespresso\b", r"\bboba\b",
    ]),
    ("food_and_drink", "fast_food", [
        r"mcdonald", r"chipotle", r"chick.fil.a", r"taco\s*bell", r"subway\b", r"panda\s*express",
        r"burger\s*(king|joint)", r"wendy'?s", r"in.n.out", r"five\s*guys", r"domino'?s",
        r"pizza\s*(hut|papa)", r"papa\s*john", r"\bkfc\b", r"\bpopeyes\b", r"\bsonic\s*drive\b",
        r"\bjack\s*in\s*the\s*box\b", r"\bdel\s*taco\b", r"\bjimmy\s*john", r"\bjersey\s*mike",
        r"panera", r"\bquiznos\b",
    ]),
    ("food_and_drink", "alcohol", [
        r"\bliquor\b", r"\bwine\s*(shop|&|and|cellar|merchant)\b", r"\bbrewery\b", r"\bbrewing\s*co\b",
        r"\bbeverages?\s*&?\s*more\b", r"\bbevmo\b", r"\btotal\s*wine\b", r"\bdistillery\b",
    ]),
    ("food_and_drink", "restaurant", [
        r"doordash", r"uber\s*eat", r"grubhub", r"postmates", r"seamless", r"caviar\b",
        r"chownow", r"toast\s*tab", r"tst\*", r"restaurant", r"eatery", r"bistro", r"brasserie",
        r"tavern", r"diner\b", r"grill\b", r"cantina", r"trattoria", r"steakhouse",
        r"\bsushi\b", r"\bramen\b", r"\bpoke\b", r"\bpho\b", r"\bthai\b", r"\bizakaya\b",
        r"bakery", r"patisserie", r"bar\s*&\s*grill", r"sports\s*bar", r"\bpizza\b",
        r"\bkitchen\b", r"\bgastropub\b", r"\bnobu\b", r"\bmastro", r"\bflemings",
    ]),

    # ── Transportation ──
    ("transportation", "gas", [
        r"chevron", r"shell\b", r"\bbp\b", r"exxon", r"arco\b", r"mobil\b", r"texaco",
        r"\b76\b", r"circle\s*k", r"speedway", r"sunoco", r"\bcitgo\b", r"\bvalero\b",
        r"\bphillips\s*66\b", r"\bconoco\b", r"pilot\s*travel", r"love'?s\s*travel",
        r"gas\s*station", r"\bfuel\b",
    ]),
    ("transportation", "auto_service", [
        r"jiffy\s*lube", r"valvoline", r"midas\b", r"firestone", r"\bgoodyear\b", r"\bpep\s*boys\b",
        r"car\s*(wash|detail|repair|service)", r"oil\s*change", r"\bdiscount\s*tire\b",
        r"\bles\s*schwab\b", r"\bautomotive\b", r"\bdealership\b", r"\baudi\b", r"\bservice\s*center\b",
    ]),
    ("transportation", "auto_parts", [
        r"autozone", r"o'reilly\s*auto", r"advance\s*auto", r"napa\s*auto", r"\bcarquest\b",
    ]),
    ("transportation", "rideshare", [
        r"uber\b(?!\s*eat)", r"lyft\b", r"\btaxi\b", r"\bcab\s*co\b",
    ]),
    ("transportation", "parking_tolls", [
        r"\btoll\b", r"parking\b", r"ezpass", r"fastrak", r"\bgood\s*to\s*go\b",
        r"\bparkmobile\b", r"\bspothero\b", r"\bpaybyphone\b",
    ]),
    ("transportation", "public_transit", [
        r"\btransit\b", r"metro\s*(transit|rail|bus|card)\b", r"\bbart\b", r"\bmta\b",
        r"\bcaltrain\b", r"\bsound\s*transit\b", r"\borca\s*card\b", r"\bsubway\s*metro\b",
    ]),
    ("transportation", "registration", [
        r"\bdmv\b", r"vehicle\s*licens", r"dept.*licens", r"\btab\s*renewal\b",
    ]),

    # ── Travel ──
    ("travel", "flights", [
        r"delta\s*(air)?", r"united\s*(air)?", r"american\s*airlines?", r"southwest\s*air",
        r"jetblue", r"alaska\s*air", r"spirit\s*air", r"frontier\s*air", r"\bhawaiian\s*air\b",
        r"airline", r"\bairport\b", r"air\s*canada",
    ]),
    ("travel", "lodging", [
        r"marriott", r"hilton", r"hyatt", r"sheraton", r"wyndham", r"holiday\s*inn",
        r"best\s*western", r"hampton\s*inn", r"\bairbnb\b", r"\bvrbo\b", r"\bmotel\b",
        r"\bhotel\b(?!\s*(casino))", r"\bresort\b", r"\blodge\b", r"\binn\b",
    ]),
    ("travel", "rental_car", [
        r"rental\s*car", r"hertz\b", r"enterprise\s*rent", r"avis\b", r"budget\s*rent",
        r"\bnational\s*car\b", r"\balamo\s*rent\b", r"\bzipcar\b", r"\bturo\b",
    ]),
    ("travel", "other", [r"expedia", r"booking\.com", r"kayak\b", r"priceline", r"hotels\.com", r"amtrak", r"greyhound"]),

    # ── Subscriptions ──
    ("subscriptions", "streaming", [
        r"netflix", r"spotify", r"hulu\b", r"disney\+?", r"hbo\s*(max|now)", r"\bmax\b\s*stream",
        r"peacock\b", r"paramount\+?", r"apple\s*(tv|music|one|arcade)", r"youtube\s*(premium|tv)",
        r"amazon\s*(prime|music|video)", r"\bpandora\b(?!\s*\d{5,})", r"\btidal\b", r"\bdeezer\b", r"audible\b",
    ]),
    ("subscriptions", "software", [
        r"adobe\b", r"dropbox", r"icloud\+?", r"google\s*(one|workspace|storage)",
        r"microsoft\s*(365|office|xbox\s*game\s*pass)", r"openai\b", r"chatgpt",
        r"github\s*(copilot|pro)?", r"\bslack\b", r"\bzoom\b", r"\bnotion\b", r"\bfigma\b",
        r"\b1password\b", r"\bdashlane\b", r"\bcanva\b", r"\bgrammarly\b",
    ]),
    ("subscriptions", "news", [r"nytimes", r"\bwsj\b", r"washington\s*post", r"\bthe\s*economist\b", r"\bsubstack\b"]),
    ("subscriptions", "memberships", [
        r"linkedin\s*premium", r"ancestry\b", r"duolingo", r"headspace", r"\bcalm\b",
        r"\bmasterclass\b", r"\bcostco\s*member", r"annual\s*fee", r"\bsubscription\b",
    ]),

    # ── Entertainment ──
    ("entertainment", "movies_tv", [
        r"amc\s*theatre", r"regal\s*cine", r"cinemark", r"alamo\s*draft", r"fandango",
        r"atom\s*tickets", r"\bmovie\s*theat", r"\bcinema\b",
    ]),
    ("entertainment", "events", [
        r"ticketmaster", r"\btm\s*\*", r"stubhub", r"seatgeek", r"eventbrite", r"live\s*nation",
        r"\baxs\b", r"\bbox\s*office\b", r"\bconcert\b", r"\btheatre\b", r"\bgala\b",
    ]),
    ("entertainment", "video_games", [
        r"steam\s*(games|purchase)?", r"playstation\s*(store|network|plus)",
        r"xbox\s*(live|game\s*pass)", r"nintendo\s*(eshop|online)", r"\btwitch\b",
        r"epic\s*games", r"\briot\s*games\b", r"\broblox\b",
    ]),
    ("entertainment", "gambling", [
        r"casino", r"\bpoker\b", r"slot\s*machine", r"caesars", r"bellagio", r"mgm\s*grand",
        r"venetian\s*(hotel|resort|casino|gondola)", r"hard\s*rock\s*(casino|hotel)",
        r"mandalay\s*bay", r"wynn\s*(hotel|resort|casino|las)", r"\bdraftkings\b", r"\bfanduel\b",
    ]),
    ("entertainment", "hobbies", [
        r"bowling", r"mini\s*golf", r"go.kart", r"escape\s*room", r"laser\s*tag",
        r"trampoline\s*park", r"\bmuseum\b", r"aquarium", r"comedy\s*club", r"karaoke", r"\bzoo\b",
    ]),

    # ── Health ──
    ("health", "pharmacy", [
        r"cvs\s*(pharmacy|health)?", r"walgreen", r"rite\s*aid", r"pharmacy", r"\brx\b",
    ]),
    ("health", "dental", [r"dental\b", r"orthodont", r"\bdds\b"]),
    ("health", "vision", [r"optometry", r"vision\s*care", r"\bvisionworks\b", r"\blenscrafters\b", r"\bwarby\s*parker\b"]),
    ("health", "mental_health", [r"therapy", r"psychiatr", r"psycholog", r"\bcounseling\b", r"\bbetterhelp\b", r"\btalkspace\b"]),
    ("health", "fitness", [
        r"\bgym\b", r"fitness", r"\bpeloton\b", r"\bequinox\b", r"\bla\s*fitness\b",
        r"24\s*hour\s*fit", r"planet\s*fitness", r"\bcrossfit\b", r"\byoga\b", r"\bpilates\b",
    ]),
    ("health", "doctor", [
        r"hospital", r"urgent\s*care", r"emergency\s*(room|care)", r"medical\s*(center|group|clinic)",
        r"health\s*system", r"dermatol", r"chiropract", r"labcorp", r"quest\s*diagnostics",
        r"\bclinic\b", r"\bphysician", r"\bmd\b", r"copay",
    ]),

    # ── Personal care ──
    ("personal_care", "hair_beauty", [
        r"\bsalon\b", r"\bbarber\b", r"\bhair\b", r"\bnails?\b", r"\bsephora\b", r"\bulta\b",
        r"\bcosmetic", r"\bbeauty\b",
    ]),
    ("personal_care", "spa_massage", [r"\bspa\b", r"\bmassage\b", r"\bmani\b", r"\bpedi\b"]),
    ("personal_care", "laundry", [r"\blaundry\b", r"dry\s*clean", r"\blaundromat\b"]),

    # ── Education & childcare ──
    ("education", "childcare", [r"\bdaycare\b", r"child\s*care", r"\bpreschool\b", r"\bkindercare\b", r"\bbright\s*horizons\b"]),
    ("education", "tuition", [r"\btuition\b", r"\buniversity\b", r"\bcollege\b", r"\bschool\s*dist", r"\bacademy\b"]),
    ("education", "supplies", [r"\bschool\s*suppl", r"\bscholastic\b"]),

    # ── Pets ──
    ("pets", "vet", [r"\bvet\b", r"veterinar", r"animal\s*(hospital|clinic)"]),
    ("pets", "pet_supplies", [r"chewy\b", r"petco", r"petsmart", r"\bpet\s*suppl", r"\bpetfood\b"]),

    # ── Taxes & government ──
    ("taxes", "vehicle_licensing", [r"vehicle\s*licens", r"\bdol\b", r"dept.*licens"]),
    ("taxes", "income_tax", [r"\birs\b", r"\bus\s*treasury\b", r"tax\s*payment", r"\bfranchise\s*tax\b", r"\bdept\s*of\s*revenue\b"]),
    ("taxes", "property_tax", [r"property\s*tax", r"county\s*treasurer", r"county\s*tax"]),
    ("taxes", "gov_fees", [r"\bgov\b.*fee", r"\bpassport\b", r"\bcity\s*of\b.*\b(fee|util|pay)"]),

    # ── Gifts & donations ──
    ("gifts_donations", "charity", [
        r"\bdonation\b", r"\bdonate\b", r"red\s*cross", r"\bunicef\b", r"\bgofundme\b",
        r"\bgoodwill\b", r"\bsalvation\s*army\b", r"\bchurch\b", r"\bcharity\b", r"\bfoundation\b",
    ]),

    # ── Financial / professional ──
    ("financial", "interest_charge", [r"interest\s*charge", r"finance\s*charge", r"\binterest\b.*\bcharged\b"]),
    ("financial", "bank_fees", [
        r"\boverdraft\b", r"\bnsf\s*fee\b", r"monthly\s*(service|maint)\s*fee", r"atm\s*fee",
        r"foreign\s*transaction\s*fee", r"\bwire\s*fee\b", r"\bservice\s*charge\b",
    ]),
    ("financial", "professional_services", [
        r"\battorney\b", r"\blaw\s*(firm|office)\b", r"\blegal\b", r"\baccounting\b",
        r"\bcpa\b", r"tax\s*(solution|service|prep|advisor)", r"\bturbotax\b", r"\bh&r\s*block\b",
        r"\bnotary\b", r"\bconsulting\b",
    ]),

    # ── Shopping ──
    ("shopping", "online_marketplace", [
        r"amazon(?!\s*(prime|music|video))", r"amzn\b", r"etsy\b", r"ebay\b", r"poshmark",
        r"\baliexpress\b", r"\btemu\b", r"\bshein\b", r"\bmercari\b",
    ]),
    ("shopping", "electronics", [
        r"best\s*buy", r"apple\s*store", r"\bmicro\s*center\b", r"\bnewegg\b", r"\bgamestop\b",
        r"\bb&h\s*photo\b", r"\bsamsung\b.*store",
    ]),
    ("shopping", "department_store", [
        r"macy'?s", r"nordstrom", r"bloomingdale", r"\bkohl'?s\b", r"\bjcpenney\b",
        r"\bdillard'?s\b", r"\bsaks\b", r"\bneiman\s*marcus\b",
        r"walmart(?!\s*(grocery|superstore))", r"target\b",
    ]),
    ("shopping", "clothing", [
        r"tj\s*maxx", r"marshalls", r"ross\s*stores", r"gap\b", r"old\s*navy", r"banana\s*republic",
        r"h\s*&\s*m\b", r"zara\b", r"uniqlo", r"forever\s*21", r"nike\b", r"adidas\b",
        r"foot\s*locker", r"\blululemon\b", r"\bgucci\b", r"\bprada\b", r"louis\s*vuitton",
        r"\bchanel\b", r"\bversace\b", r"\bburberry\b", r"\bhermes\b", r"\bfendi\b",
        r"\bbalenciaga\b", r"saint\s*laurent", r"\bdior\b", r"tiffany\s*&\s*co",
        r"\bclothing\b", r"\bapparel\b", r"\bboutique\b",
    ]),
    ("shopping", "home_goods", [
        r"bed\s*bath", r"container\s*store", r"\bhomegoods\b", r"\bworld\s*market\b",
        r"\bbed\s*bath\s*&\s*beyond\b",
    ]),
    ("shopping", "sporting_goods", [
        r"\brei\b", r"dick'?s\s*sporting", r"\bsporting\s*goods\b", r"\bacademy\s*sports\b",
        r"\bbass\s*pro\b", r"\bcabela'?s\b",
    ]),
    ("shopping", "general_merchandise", [
        r"dollar\s*(tree|general)", r"\bfive\s*below\b", r"\bbig\s*lots\b",
    ]),
]

_COMPILED: list[tuple[str, str, list[re.Pattern]]] = [
    (primary, sub, [re.compile(p, re.IGNORECASE) for p in pats])
    for primary, sub, pats in _RULES
]


def categorize_expense(description: str) -> tuple[str, str, str]:
    """Map a transaction description to ``(primary, subcategory, source)``.

    ``source`` is ``"rule"`` on a match, or ``"fallback"`` when nothing matches
    (returning ``("other", "other", "fallback")``). The AI categorizer picks up
    fallback rows for the long tail.
    """
    for primary, sub, patterns in _COMPILED:
        for pat in patterns:
            if pat.search(description):
                return primary, sub, "rule"
    return "other", "other", "fallback"
