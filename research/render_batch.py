#!/usr/bin/env python3
"""Batch driver: render a set of stories through carousel_render's v5 "bold & human"
templates. Generalizes render_pilot.py (which was hardcoded to the Zepto pilot) so new
stories can be added by dropping a config dict into STORIES, instead of writing a new
one-off script per story.

Each story config supplies:
  - content: path to the generate_content.py JSON for that story
  - cover_bg / backstory_bg: background image paths (real photos or AI-generated backdrops)
  - headlines: dict of slide-key -> retrofitted headline with **phrase** accent markup
    (content JSON predates the markup convention landing in generate_content.py's prompt,
    same situation the Zepto pilot was in)
  - chart / timeline / news_stat: pick exactly one per story for the news-slide aside,
    based on what that story's own data actually supports -- a real before/after number
    (chart), a multi-year sequence of turning points (timeline), or one striking number
    that isn't a comparison (news_stat). Never force a chart where the underlying numbers
    aren't a genuine two-value comparison.
  - stat: optional (value, caption) for the why-slide numeral card
  - logo: optional path to a clean logo file; omitted entirely for stories where no real
    logo asset exists rather than fetching one from the web
"""
import json
from pathlib import Path

from carousel_render import (
    cover_slide, backstory_slide, news_slide, why_slide, engage_slide, render_to_png,
)

HERE = Path(__file__).parent
CONTENT_DIR = HERE / "content"
OUT = HERE / "assets" / "code_pilot"

# Rewritten copy pass (all 24 stories below, Zepto's equivalent lives in render_pilot.py):
# deeper, more cinematic/analytical voice than the flat fact-recitation of the source JSON,
# per feedback that the original pass read as "too much infographic and repeated or
# unnecessary numbers" with insufficient narrative depth. Every fact here is grounded in the
# same source JSON / sources_used citations already researched; nothing is invented. Keyed
# by slug, applied as an override at render time only -- the content JSON itself is untouched.
BODIES = {
    "icici": {
        "slide2_body": (
            "ICICI began in 1955 as a World Bank-funded vehicle to bankroll India's "
            "industrial buildout, a policy tool more than a bank. Four decades later it "
            "privatized, rebuilt itself around retail lending and technology, and is now "
            "India's second-largest bank by assets, chasing a crown HDFC has held for years."
        ),
        "slide3_body": (
            "ICICI just posted its biggest profit quarter ever, ₹14,805 crore, up 16% year "
            "on year, even as the RBI has been cutting rates that should be squeezing what "
            "banks earn on loans. Advances grew 19.6% to ₹16.3 lakh crore, meaning the bank "
            "is lending more and still protecting its margins."
        ),
        "slide4_bullets": [
            "Margins expanding while rates fall is the opposite of what textbook banking predicts, and it's happening anyway",
            "Bad loans keep shrinking, a sign this growth isn't built on riskier lending",
            "₹22,963 crore parked as a buffer, well beyond what's needed, banking on caution paying off later",
        ],
        "slide5_headline": (
            "ICICI is out-growing HDFC Bank on profit this quarter, in a rate environment "
            "that's supposed to squeeze both of them equally. Is that just better execution, "
            "or is India's **private banking pecking order** actually about to flip?"
        ),
    },
    "netflix": {
        "slide2_body": (
            "A year ago, Netflix was riding an all-time high on the backs of Stranger "
            "Things and Squid Game, looking less like a streaming service than an "
            "entertainment monopoly. Then the hits slowed, a bid to swallow Warner Bros. "
            "Discovery collapsed, and the question investors had stopped asking, what "
            "happens when the slate goes quiet, came roaring back."
        ),
        "slide3_body": (
            "Netflix delivered exactly what Wall Street expected this quarter, $12.56 "
            "billion in revenue, up 13%. It was the forecast for the next one that broke "
            "the spell: guidance for Q3 came in soft enough to send shares down 13% in a "
            "day, their worst level in almost two years."
        ),
        "slide4_bullets": [
            "At 20 times earnings, Netflix is priced like a company that never slows down, so any wobble gets punished hard",
            "Choosing this exact moment to share less viewership data reads as bad timing at best",
            "Ads were supposed to be the next growth engine; they're still just $3B of a $51B business",
        ],
        "slide5_headline": (
            "Netflix is leaning harder into ads and live sports while giving investors "
            "less visibility into what's actually working. Is the stock still priced for "
            "**a growth story**, or is the market just now catching up to a maturing one?"
        ),
    },
    "apple-nvidia": {
        "slide2_body": (
            "Apple got to a trillion dollars first, in 2018, on the strength of a hardware "
            "franchise it had spent a decade perfecting. Then AI arrived, and the market "
            "decided the real prize wasn't the device people used, it was the chips "
            "training the models underneath. Nvidia overtook Apple in 2024 and kept "
            "climbing, touching $5 trillion in 2025."
        ),
        "slide3_body": (
            "Apple didn't out-execute Nvidia this week so much as watch it stumble, a 3.5% "
            "drop was enough to hand Apple the title back at $4.88 trillion to Nvidia's "
            "$4.86 trillion. The gap is a rounding error, but the symbolism, Apple on top "
            "of the AI trade without shipping an AI chip, is not."
        ),
        "slide4_bullets": [
            "The market may be signaling that AI's biggest winners won't just be the companies selling the picks and shovels",
            "Nvidia's business hasn't weakened; this is a valuation swing, not a verdict on its chips",
            "Two companies separated by a rounding error means the top spot is up for grabs every quarter",
        ],
        "slide5_headline": (
            "Apple just reclaimed the world's most valuable company title without shipping "
            "a single AI model of its own. Does that mean the AI trade is really about who "
            "**monetizes it best**, not who builds it?"
        ),
    },
    "deepseek": {
        "slide2_body": (
            "Liang Wenfeng built DeepSeek in 2023 as a side project funded out of his own "
            "hedge fund's pocket, a research bet with no outside investors to answer to. "
            "Then in January 2025, its R1 model matched Silicon Valley's best at a "
            "fraction of the cost, and in a single day wiped $500 billion off US AI stocks."
        ),
        "slide3_body": (
            "DeepSeek is back raising money, this time at a $74 billion valuation, Reuters "
            "reported on July 15. That's an $8 billion jump from the $66 billion tag it "
            "carried just weeks ago in its first-ever outside funding round, a pace that "
            "suggests investors aren't waiting to see if the hype holds."
        ),
        "slide4_bullets": [
            "The company that proved AI didn't need billions is now raising billions; cheap AI was never going to stay cheap at this scale",
            "It's building its own chips and doubling headcount, the moves of a company preparing to compete for years, not one quarter",
            "A future STAR Market listing would make DeepSeek China's clearest answer yet to OpenAI going public",
        ],
        "slide5_headline": (
            "DeepSeek's whole pitch was that great AI didn't need Silicon Valley money. Now "
            "it's raised $7.4 billion in weeks and is chasing a $74 billion valuation. Was "
            "'**cheap AI**' ever the real story, or just the opening chapter?"
        ),
    },
    "mahindra-it": {
        "slide2_body": (
            "For two years, every earnings call in India's $200 billion IT industry has "
            "carried the same undercurrent of dread, that AI would do to coders what "
            "automation did to factory floors. So when Tech Mahindra's chairman took the "
            "stage at its 39th AGM, the industry was listening for a verdict, not a speech."
        ),
        "slide3_body": (
            "Anand Mahindra didn't hedge. AI, he argued, won't shrink IT services, it will "
            "make them indispensable, because the world's businesses still run on decades "
            "of tangled legacy systems that AI alone can't untangle. Someone has to wire "
            "the new intelligence into the old plumbing, and that's still a services company."
        ),
        "slide4_bullets": [
            "The real shift isn't fewer IT jobs, it's coders becoming the people who manage AI inside messy, decades-old systems",
            "The government backing Tech Mahindra for its national AI mission is a vote of confidence, not just a talking point",
            "It's a direct answer to the anxiety sitting under 5 million Indian IT jobs, even if the proof is still years away",
        ],
        "slide5_headline": (
            "Mahindra says AI will make India's IT industry more essential, not obsolete. "
            "Is that a genuine strategic bet, or the reassurance a **$200 billion industry** "
            "has to tell itself while it figures out the real answer?"
        ),
    },
    "armory": {
        "slide2_body": (
            "Along India's borders, drones had quietly become the smugglers' tool of "
            "choice, slipping weapons and drugs past checkpoints built for people, not "
            "aircraft. In 2024, IIT Bombay graduate Amardeep Singh looked at a threat the "
            "defence establishment was still studying and built a company to answer it "
            "instead."
        ),
        "slide3_body": (
            "Two years after founding, Armory just won three Ministry of Defence contracts "
            "worth ₹100 crore for SURGE, a counter-drone system that can spot incoming "
            "drones 5 km out and jam them from 3 km away. For a company that young, landing "
            "a defence order at all is the news; landing three at once is the signal."
        ),
        "slide4_bullets": [
            "The Ministry of Defence choosing a 2-year-old startup over its usual large contractors is the real headline here",
            "It puts Armory in a defence-tech sector racing to build capability faster than procurement cycles usually allow",
            "Next up: hard-kill drone tech and a fresh fundraise, the two things that turn one order into a defence business",
        ],
        "slide5_headline": (
            "A 2-year-old startup just won a ₹100 crore defence order the old guard didn't "
            "get. Should India's military keep betting on speed over experience, or is that "
            "exactly the kind of shortcut **national security** can't afford?"
        ),
    },
    "kimi": {
        "slide2_body": (
            "Moonshot AI was just another Chinese lab in 2023, one of dozens racing to "
            "catch up to OpenAI, led by ex-Google researcher Yang Zhilin. By May 2026 it "
            "had raised $2 billion at a $20 billion valuation, money that bought it the "
            "compute to stop catching up and start competing directly."
        ),
        "slide3_body": (
            "On July 16, Moonshot released Kimi K3, a 2.8 trillion parameter model, the "
            "largest open-weight AI ever built. It didn't ease into the leaderboards, it "
            "went straight to #1 on a top coding benchmark, ahead of both Claude and "
            "GPT-5.6, models built by companies with far deeper pockets."
        ),
        "slide4_bullets": [
            "Beating Claude while costing 5x less breaks the assumption that better AI has to mean more expensive AI",
            "Nasdaq fell 1.4% the next day; markets read this as a real threat, not a PR stunt",
            "The full model goes open and free on July 27, so any developer can verify the claims themselves",
        ],
        "slide5_headline": (
            "A Chinese open model just topped a coding leaderboard at a fifth of Claude's "
            "price. If the performance holds once it's fully open on July 27, what's left "
            "of the **moat** US AI labs have been charging premium prices for?"
        ),
    },
    "fedex-raj": {
        "slide2_body": (
            "Raj Subramaniam did everything the credential-obsessed version of success "
            "demands, an IIT Bombay degree, then two more from Syracuse and UT Austin. "
            "None of it mattered in 1991, when he walked into a job market gutted by "
            "recession, holding a resume that looked exactly like everyone else's."
        ),
        "slide3_body": (
            "The break came by accident. In 1991, Raj overheard his roommate decline a "
            "FedEx interview slot and, without much thought, took the call himself. That "
            "impulsive minute got him a job in Memphis, and three decades later, in 2022, "
            "made him only the second CEO in FedEx's history."
        ),
        "slide4_bullets": [
            "FedEx stock has doubled since he took over, evidence the accidental hire became a deliberate leader",
            "He now runs an operation of 500,000+ people across 220+ countries, a scale most CEOs never inherit, let alone earn by chance",
            "His degrees got him in rooms; the one moment he acted on instinct is what actually changed his life",
        ],
        "slide5_headline": (
            "Raj had an IIT degree and two American ones, and still almost missed his shot "
            "until he grabbed a call meant for someone else. If credentials didn't make the "
            "difference, what actually did, and are you positioned to notice **your own "
            "version of that call**?"
        ),
    },
    "rbi-plastic-notes": {
        "slide2_body": (
            "India already tried this once. In 2012, a billion plastic ₹10 notes went into "
            "circulation across five cities as a pilot, only to get quietly shelved because "
            "the country's ATMs, built for thinner paper, jammed on the new plastic. The "
            "idea didn't fail, the infrastructure around it did."
        ),
        "slide3_body": (
            "Fourteen years later, RBI's printing arm is trying again, inviting suppliers "
            "to bid by August 18 for polymer note material. This time the target is "
            "deliberate: ₹10 and ₹20 notes, the smallest denominations, because they're the "
            "ones that pass through the most hands and wear out the fastest."
        ),
        "slide4_bullets": [
            "23.8 billion worn notes were pulled from circulation and destroyed in FY25 alone, the cost paper currency quietly imposes every year",
            "Polymer notes last roughly 2.5x longer, a straightforward argument for cutting that cost, if the ATM problem is actually solved this time",
            "60+ countries already use polymer currency, partly because it's far harder to counterfeit than paper",
        ],
        "slide5_headline": (
            "India tried plastic currency once and the ATMs couldn't handle it. If a ₹10 "
            "note can now survive a wash and outlast paper by 2.5x, is durability worth "
            "**rethinking how India uses cash**?"
        ),
    },
    "jio-financial": {
        "slide2_body": (
            "When Jio Financial split off from Reliance in 2023, it inherited a balance "
            "sheet and a licence to operate in lending, payments, and insurance, but not "
            "much else. Investors treated it as a placeholder stock for two years, waiting "
            "for proof it could actually grow instead of just exist."
        ),
        "slide3_body": (
            "This quarter is the proof investors were waiting for. Profit rose 156% to Rs "
            "830 crore, lending assets grew 2.6x, and the JioFinance app crossed 25 million "
            "users, numbers that read less like a slow-building fintech and more like one "
            "that just found its footing all at once."
        ),
        "slide4_bullets": [
            "Motilal Oswal reiterated Buy with a Rs 315 target, implying 34% more upside from here",
            "Geojit's Rs 273 target is more conservative but still bullish on the broader growth story",
            "The real test is next quarter: rising operating expenses could eat into a growth rate this good",
        ],
        "slide5_headline": (
            "Jio Financial just posted 156% profit growth after two years of investors "
            "wondering if it would ever move. Is this the quarter the thesis finally proves "
            "out, or does **one strong number** just buy it more patience?"
        ),
    },
    "jio-ipo-marketing": {
        "slide2_body": (
            "Mukesh Ambani first floated the idea of listing Jio back in 2019, then let it "
            "sit for years while the company kept growing quietly underneath the promise. "
            "The commitment finally turned real this year, with Jio filing its draft IPO "
            "papers with SEBI on June 19, seven years after the idea was first said out loud."
        ),
        "slide3_body": (
            "Next week, right after its Q1 numbers land, Jio starts informal meetings with "
            "big investors, the soft marketing that precedes any roadshow. The scale of "
            "what's being sold is the real story: bankers are pricing Jio anywhere between "
            "$100 billion and $180 billion, an 80% spread that shows just how unprecedented "
            "this listing is."
        ),
        "slide4_bullets": [
            "This could overtake Hyundai's listing as India's biggest IPO ever, by a wide margin",
            "Rs 27,500 crore of the proceeds go straight to cutting telecom debt, not just funding growth",
            "A run of large, well-received IPOs recently gives Jio's bankers more room to push for a premium price",
        ],
        "slide5_headline": (
            "Bankers can't agree if Jio is worth $100 billion or $180 billion, an 80% gap on "
            "India's biggest-ever listing. When the range is this wide, is the market still "
            "pricing a company, or **just guessing at appetite**?"
        ),
    },
    "jsw-steel": {
        "slide2_body": (
            "For months, JSW Steel had been fighting a squeeze familiar to every "
            "steelmaker: prices too soft to protect margins, costs too high to ignore. "
            "Analysts had priced in a modest recovery this quarter, nothing that would "
            "change the narrative of an industry grinding through a rough patch."
        ),
        "slide3_body": (
            "The recovery analysts modeled didn't happen, a much bigger one did. Profit "
            "came in at ₹4,696 crore, more than double last year's ₹2,209 crore, while "
            "revenue climbed 9.8% to ₹47,364 crore, blowing past every estimate on the "
            "street."
        ),
        "slide4_bullets": [
            "Sales volumes, not just prices, drove this beat, evidence of real demand rather than a lucky pricing quarter",
            "Falling debt means JSW can keep funding its expansion without leaning harder on the balance sheet",
            "A beat this size in a core industrial input is usually a read on the broader economy, not just one company",
        ],
        "slide5_headline": (
            "JSW Steel didn't just beat estimates, it blew past them by over ₹1,100 crore "
            "while still funding aggressive expansion. Is Indian steel entering a real "
            "**supercycle**, or is one great quarter getting mistaken for a trend?"
        ),
    },
    "makemytrip-ipo": {
        "slide2_body": (
            "MakeMyTrip built its business entirely on Indian travelers, then went to "
            "Nasdaq to raise money in 2010, pulling in $80.5 million from an American "
            "market that had no particular reason to understand Indian travel booking. For "
            "sixteen years, the one group of investors who couldn't buy in was the one "
            "whose habits built the company."
        ),
        "slide3_body": (
            "That changes now. MakeMyTrip confidentially filed for an India listing on "
            "July 17, one that could raise up to $1 billion, roughly ₹8,600 crore, sixteen "
            "years after it decided America was the better place to go public."
        ),
        "slide4_bullets": [
            "Indian retail investors finally get a direct stake in a platform they've been using for two decades",
            "The raise funds growth and acquisitions, and keeps a dual listing on the table rather than choosing one market",
            "If this lands well, it becomes the case study other Nasdaq-listed Indian companies use to justify coming home",
        ],
        "slide5_headline": (
            "MakeMyTrip picked Nasdaq over India in 2010 because that's where the capital "
            "was. Sixteen years later it's filing to list at home. Does that say India's "
            "capital markets have caught up, or that **going abroad first** was always the "
            "smarter play?"
        ),
    },
    "manipal-hospitals": {
        "slide2_body": (
            "Manipal's story runs from a single medical college in Karnataka to a network "
            "of over 10,700 hospital beds, the kind of scale that turns a regional "
            "institution into a national one. In 2023, Temasek bought a majority stake at "
            "a $5 billion valuation, a bet that this growth still had years left to run."
        ),
        "slide3_body": (
            "The number has moved since then. Manipal is now targeting a valuation of "
            "roughly Rs 80,000 crore, $8.3 billion, well below the $10-12 billion range "
            "floated just months ago, even as it still plans to raise up to Rs 11,000 crore "
            "and list as early as the week of July 27."
        ),
        "slide4_bullets": [
            "Even after the cut, this is still on track to be 2026's biggest IPO, ahead of SBI Funds",
            "The proceeds go toward paying down debt and funding further hospital expansion, not just cashing out early investors",
            "A lower price tag is a cheaper entry point, if the cut reflects caution rather than real weakness in the business",
        ],
        "slide5_headline": (
            "Manipal just trimmed its own IPO valuation by nearly a third before even "
            "listing. Is that the market getting realistic about hospital economics, or a "
            "company **negotiating against itself** before investors even get a say?"
        ),
    },
    "hydrogen-train": {
        "slide2_body": (
            "Indian Railways had already electrified over 99% of its network, leaving only "
            "a stubborn handful of heritage hill routes, Darjeeling among them, still "
            "running on diesel out of necessity rather than choice. In 2023, Railways "
            "committed to 35 hydrogen trains as the answer, and picked the flat, "
            "unglamorous Jind-Sonipat stretch in Haryana to prove the technology first."
        ),
        "slide3_body": (
            "On July 17, PM Modi flagged off the NaMo Green Rail from Jind, India's first "
            "hydrogen train, built domestically, seating 2,600 passengers, and emitting "
            "nothing but water vapour on its 89 km run. It's a genuine milestone, and also, "
            "deliberately, the easiest possible test of one."
        ),
        "slide4_bullets": [
            "India joins only Germany and China in running hydrogen trains commercially, a short list to be on",
            "35 more are planned, including the harder routes this one was built to derisk, Darjeeling and the Nilgiri hills",
            "The fuel cell, the actual engine of the technology, is still imported, and green hydrogen remains expensive to produce",
            "Germany's own hydrogen fleet has struggled with fuel cell wear, a preview of the maintenance reality ahead",
        ],
        "slide5_headline": (
            "India built the train body but still imports the fuel cell that actually "
            "powers it. Is this a genuine 'Make in India' milestone, or a first step being "
            "sold as **the finish line**?"
        ),
    },
    "reliance-jio-q1": {
        "slide2_body": (
            "Jio launched in 2016 by giving away data and calls for free, a move that "
            "crashed the price of a gigabyte in India from Rs 250 to under Rs 10 and "
            "rewired how an entire country used the internet. By 2020, Reliance had spun it "
            "off as Jio Platforms and pulled in over $20 billion from Meta, Google, and "
            "others betting the disruption wasn't finished."
        ),
        "slide3_body": (
            "The numbers ahead of Jio's IPO show a company that's stopped competing purely "
            "on scale and started competing on price per user: profit up 9.2% to Rs 7,764 "
            "crore, revenue up 12% to Rs 45,961 crore, and ARPU climbing to Rs 215.6 even "
            "as it still added 8.9 million users to reach 533.3 million."
        ),
        "slide4_bullets": [
            "Rising ARPU alongside user growth is the exact combination IPO investors want to see, more per user, not just more users",
            "Broadband market share crossed 43%, making Jio India's leader there too, not just in mobile",
            "AirFiber alone drove over 75% of new broadband signups, Jio's fixed-wireless bet paying off fast",
            "Akash Ambani is pitching Jio's patent portfolio as tech IP, not telecom infrastructure, ahead of the listing",
        ],
        "slide5_headline": (
            "Jio wants IPO investors to value it like a technology company, not a phone "
            "carrier. The numbers show rising ARPU and a patent pitch to match. Is that a "
            "real repositioning, or still **telecom economics** wearing a tech story?"
        ),
    },
    "reliance-retail-q1": {
        "slide2_body": (
            "Reliance's first attempt at quick commerce, JioMart Express, launched in 2022 "
            "and quietly shut down within a year, proof that even India's largest retailer "
            "couldn't just will its way into the category. It came back in late 2024 with "
            "zero delivery fees, a blunt instrument aimed squarely at Blinkit, Zepto, and "
            "Swiggy Instamart."
        ),
        "slide3_body": (
            "The bill for that second attempt came due this quarter. Revenue rose 7.4% to "
            "Rs 90,408 crore, but profit fell 14.2% to Rs 2,806 crore, quick commerce "
            "spending eating directly into margins even as the company kept expanding, "
            "adding 252 new stores along the way."
        ),
        "slide4_bullets": [
            "JioMart is now closing in on India's #2 quick-commerce spot, the payoff this profit hit is meant to buy",
            "Zero delivery fees only make sense as a price war; a real feature would have a shelf life, this doesn't",
            "Management is still guiding to double retail EBITDA within three years, betting the margin pain is temporary",
            "Digital already drives over a quarter of fashion sales, proof the online push is working beyond just groceries",
        ],
        "slide5_headline": (
            "Reliance is taking a 14% profit hit on purpose to buy market share from "
            "Blinkit and Zepto. Is that patient capital playing a longer game than its "
            "rivals can afford, or **margin bleed with no obvious exit**?"
        ),
    },
    "ril-q1": {
        "slide2_body": (
            "Reliance's evolution from an oil and textiles company into a conglomerate "
            "spanning energy, telecom, and retail is old news by now. What matters this "
            "quarter is the comparison it's up against: last year's profit included a "
            "one-time Rs 8,924 crore gain from selling its Asian Paints stake, a number "
            "that flatters nothing except the year-ago base."
        ),
        "slide3_body": (
            "Revenue crossed ₹3 lakh crore for the first time, up 25% year on year, and "
            "EBITDA rose 10% to ₹54,067 crore, the numbers that actually reflect the "
            "business. Net profit fell 22% to ₹20,946 crore, but only because last year "
            "had a one-off gain this year didn't repeat, strip that out and the core "
            "business grew."
        ),
        "slide4_bullets": [
            "Jio's coming ₹37,700 crore IPO is the reason this quarter's telecom numbers matter beyond Reliance's own books",
            "533 million users and rising prices per user means Jio is monetizing scale it built years ago",
            "The oil-to-chemicals business hit a 4-year high in profit, the unglamorous unit quietly funding everything else",
        ],
        "slide5_headline": (
            "Reliance's headline profit fell 22%, but only because of an accounting quirk, "
            "its actual business grew. When the number that grabs headlines and the number "
            "that matters point opposite ways, **which one should investors trust**?"
        ),
    },
    "skyroot": {
        "slide2_body": (
            "For as long as India has had a space program, ISRO was the only one allowed "
            "to run it, a state monopoly that didn't crack open until 2020. Two years "
            "before that door opened, ex-ISRO engineers Pawan Kumar Chandana and Naga "
            "Bharath Daka had already founded Skyroot, betting the door would open before "
            "they ran out of funding. It did, and by 2022 they'd reached space on a test "
            "flight."
        ),
        "slide3_body": (
            "On July 18, Vikram-1 lifted off from Sriharikota and did what no Indian "
            "private company had done before, ran through all four stages cleanly in 17 "
            "minutes and placed satellites into orbit 450 km up. The bet Chandana and Daka "
            "made in 2018, before the rules even allowed it, just paid off in full."
        ),
        "slide4_bullets": [
            "Skyroot is already planning 4 to 6 more launches this year, treating this as a start, not a victory lap",
            "India's space economy is projected to hit $44 billion by 2033, and Skyroot just proved it can compete for that market",
            "A 30% government subsidy gives Skyroot a real cost edge over rivals building without that support",
        ],
        "slide5_headline": (
            "A private Indian company just did what only ISRO had ever done. Does that "
            "make ISRO's decades of monopoly look like it held the sector back, or does it "
            "prove the monopoly **built the expertise** this moment needed?"
        ),
    },
    "copper": {
        "slide2_body": (
            "Copper spent decades as the most boring commodity in the world, useful, "
            "essential, and never the subject of anyone's excitement. That changed the "
            "moment EVs, solar farms, wind turbines, and AI data centers all started "
            "needing far more of it at once, turning a metal nobody thought about into one "
            "nobody can get enough of."
        ),
        "slide3_body": (
            "The IEA now projects a 30% global copper supply shortfall by 2035, not a "
            "forecast of tight markets, but of outright scarcity. New mines are getting "
            "harder to find and slower to permit, which is why Goldman Sachs sees prices "
            "climbing toward $15,000 a tonne by 2035, up from roughly $10,000-13,000 today."
        ),
        "slide4_bullets": [
            "India's own 500 GW clean energy target depends on a metal it doesn't produce enough of domestically",
            "AI data centers alone could need 550,000 tonnes of copper by 2030, a demand source that didn't exist a decade ago",
            "Governments are starting to treat copper access as a national security question, not just a commodities one",
        ],
        "slide5_headline": (
            "India imports over half its copper while sitting on reserves it hasn't "
            "touched. If the world is genuinely facing a 30% shortfall by 2035, is leaving "
            "that copper in the ground caution, or **a bet India can't afford**?"
        ),
    },
    "china-investment-policy": {
        "slide2_body": (
            "After the 2020 border clashes, India shut the door on Chinese capital almost "
            "overnight, tightening investment rules and staying out of the RCEP trade bloc "
            "entirely. Six years later, the trade relationship the wall was supposed to "
            "rebalance looks the same as ever: India imports heavily from China and "
            "exports back very little."
        ),
        "slide3_body": (
            "Rakesh Mohan, one of PM Modi's own economic advisers, is now arguing the wall "
            "didn't work as intended. He wants India to ease Chinese investment curbs "
            "specifically in textiles and footwear, revisit joining RCEP, and pursue "
            "membership in the CPTPP instead, a notable reversal coming from inside the tent."
        ),
        "slide4_bullets": [
            "That this is coming from a government adviser, not an outside critic, is what makes it notable",
            "Manufacturing jobs are the actual prize, if Chinese capital and expertise can be brought in without repeating 2020's risks",
            "Diversifying away from US trade dependence looks a lot more urgent now than before the current tariff fights",
        ],
        "slide5_headline": (
            "A Modi adviser is now arguing India should let more Chinese money into its "
            "factories, six years after the border clashes that closed that door. Is that "
            "pragmatism catching up with economics, or a risk being rationalized because "
            "**Washington got harder to deal with**?"
        ),
    },
    "us-tariffs-bill": {
        "slide2_body": (
            "Since the Ukraine war began, Russia has been selling oil to Asia at prices too "
            "good for import-dependent economies to refuse. India and China became the "
            "biggest buyers of that discounted crude, and India has defended every barrel "
            "as a matter of energy security, not politics, even as the politics kept "
            "building around it."
        ),
        "slide3_body": (
            "That politics just arrived in bill form. A bipartisan proposal from Senators "
            "Richard Blumenthal and the late Lindsey Graham, backed by over 60 members of "
            "Congress, would slap 100% tariffs on the five biggest buyers of Russian oil "
            "and gas, India and China among them."
        ),
        "slide4_bullets": [
            "This is Congress's first attempt to use trade tariffs as a direct weapon against a war, not just a trade dispute",
            "The goal is blunt: cut off the revenue funding Russia's war by making its biggest customers pay a price for buying",
            "For India, it turns a purely economic decision, cheap oil, into a geopolitical one it can no longer treat as neutral",
        ],
        "slide5_headline": (
            "Congress wants to punish India for buying cheap Russian oil with 100% "
            "tariffs, a bill that turns energy security into a geopolitical liability "
            "overnight. Should India keep prioritizing its own energy costs, or is **that "
            "math about to change**?"
        ),
    },
    "chip-bear-market": {
        "slide2_body": (
            "From March to June 2026, chip stocks surged 105% on a simple bet: that AI "
            "demand would keep compounding indefinitely and every chip made would find a "
            "buyer. The market had made this exact bet before. In January 2025, China's "
            "DeepSeek punctured it in a single day, wiping $590 billion off Nvidia alone."
        ),
        "slide3_body": (
            "It happened again. On July 17, China's Moonshot AI launched Kimi K3, a cheap "
            "model performing at the level of the best US systems, and Wall Street's chip "
            "index fell over 20% from its June peak, erasing $3.3 trillion in value across "
            "Nvidia, AMD, and TSMC."
        ),
        "slide4_bullets": [
            "Every time a cheap model matches an expensive one, it undercuts the argument that AI demand justifies unlimited chip spending",
            "The full Kimi K3 release on July 27 is the actual test; right now the market is reacting to a claim, not verified performance",
            "Big Tech earnings on July 22 land right in the middle of this selloff, and could either calm it or make it worse",
        ],
        "slide5_headline": (
            "DeepSeek crashed chip stocks in January 2025 and the market recovered within "
            "weeks. Kimi K3 just did it again. Is this selloff going to reverse the same "
            "way, or is the market finally pricing in that **cheap AI keeps happening**?"
        ),
    },
    "yes-bank": {
        "slide2_body": (
            "In 2018, Yes Bank's stock touched ₹370 and it was, briefly, India's "
            "fastest-growing private bank, the kind of growth story every analyst wanted "
            "to own. Two years later, a pile of bad loans and depositors racing for the "
            "exits forced the RBI to cap withdrawals at ₹50,000, a freeze lifted only "
            "after SBI led a ₹10,000 crore rescue."
        ),
        "slide3_body": (
            "Six years on, the numbers finally look like recovery rather than survival: "
            "profit up 34% to Rs 1,071 crore, net interest income up 17.5%, bad loans "
            "still shrinking. Moody's, CARE, and ICRA had already upgraded the bank; this "
            "quarter, S&P joined them."
        ),
        "slide4_bullets": [
            "Japan's SMBC now owns 24% of the bank, foreign capital betting the recovery is durable, not cosmetic",
            "Ratings upgrades translate directly into cheaper funding, a real financial dividend from the turnaround",
            "Few banks that come this close to collapse ever fully recover; Yes Bank is the rare case that did",
        ],
        "slide5_headline": (
            "A Japanese bank now owns a bigger stake in Yes Bank than the Indian "
            "institutions that rescued it in 2020. Is that proof India's banking system can "
            "engineer a real recovery, or a reminder of **who ends up owning the upside** "
            "when the rescue is done?"
        ),
    },
}

STORIES = [
    {
        "slug": "icici",
        "content": "content_2026-07-18_icici-bank-q1-results-profit-jumps-16-yoy-to-rs-14-805-crore.json",
        "cover_bg": OUT.parent / "covers" / "icici-tower.png",
        "backstory_bg": OUT.parent / "covers" / "icici-lobby.png",
        "logo": None,
        "headlines": {
            "slide1_label": "ICICI Bank's Biggest **Profit Quarter Ever**",
            "slide2_headline": "From World Bank Project to **Profit Machine**",
            "slide3_headline": "Q1 FY27: **16% Profit Jump**, Margins Expand",
            "slide4_headline": "Why India Should Care About **This Number**",
            "slide5_headline": (
                "ICICI is beating HDFC Bank on profit growth this quarter. Is India's "
                "**private banking crown** about to change hands?"
            ),
        },
        "chart": [
            {"value": 12763, "display": "₹12,763 Cr"},
            {"value": 14805, "display": "₹14,805 Cr", "accent": True},
        ],
        "stat": ("₹16.3 Lakh Cr", "Total Advances"),
    },
    {
        "slug": "netflix",
        "content": "content_2026-07-18_netflix-shares-tumble-13-after-weak-sales-forecast-hit-22-mo.json",
        "cover_bg": OUT.parent / "covers" / "netflix-crash.png",
        "backstory_bg": OUT.parent / "covers" / "netflix-cozy.png",
        "logo": None,
        "headlines": {
            "slide1_label": "Netflix Crashes to a **22-Month Low**",
            "slide2_headline": "From Streaming King to **Growth Doubts**",
            "slide3_headline": "Weak Forecast Triggers a **13% Crash**",
            "slide4_headline": "Growth Story Under **the Microscope**",
            "slide5_headline": (
                "Netflix is betting its future on ads and live sports while sharing less "
                "data on viewership. Is its **high stock price** still justified, or has "
                "the easy money already been made?"
            ),
        },
        "stat": ("20x", "Price To Earnings"),
    },
    {
        "slug": "apple-nvidia",
        "content": "content_2026-07-18_apple-unseats-nvidia-to-become-world-s-most-valuable-company.json",
        "cover_bg": OUT.parent / "covers" / "apple-nvidia-tower.png",
        "backstory_bg": OUT.parent / "covers" / "apple-nvidia-servers.png",
        "logo": None,
        "headlines": {
            "slide1_label": "Apple Just **Dethroned Nvidia**. Again.",
            "slide2_headline": "Nvidia's **Two-Year Reign** Atop the Market",
            "slide3_headline": "Apple Reclaims the Crown at **$4.88 Trillion**",
            "slide4_headline": "The AI Trade Is **Rotating, Not Ending**",
            "slide5_headline": (
                "Apple never built its own AI model but just passed Nvidia anyway. Is AI "
                "hype overrated, or is Apple just better at **quietly cashing in** on it?"
            ),
        },
        "timeline": [
            {"year": "2018", "text": "Apple is first to hit $1 trillion in value"},
            {"year": "2024", "text": "Nvidia overtakes Apple on the AI chip boom"},
            {"year": "2025", "text": "Nvidia races on, tops $5 trillion"},
            {"year": "2026", "text": "Apple reclaims the crown at $4.88 trillion", "accent": True},
        ],
        "stat": ("$20B", "The Entire Gap At The Top"),
    },
    {
        "slug": "deepseek",
        "content": "content_2026-07-18_china-s-deepseek-to-raise-fresh-capital-at-74-billion-valuat.json",
        "cover_bg": OUT.parent / "covers" / "deepseek.png",
        "backstory_bg": OUT.parent / "covers" / "deepseek-coder.png",
        "logo": None,
        "headlines": {
            "slide1_label": "China's DeepSeek Eyes **$74 Billion** IPO Debut",
            "slide2_headline": "From Side Project to **Global Disruptor**",
            "slide3_headline": "New Funding Round, **$74B Price Tag**",
            "slide4_headline": "AI Arms Race Gets **a New Leader**",
            "slide5_headline": (
                "DeepSeek proved you don't need billions to build great AI, then went and "
                "raised billions anyway. Was the 'cheap AI' story **always temporary**, or "
                "is this just what happens once you get serious?"
            ),
        },
        "chart": [
            {"value": 66, "display": "$66B"},
            {"value": 74, "display": "$74B", "accent": True},
        ],
        "stat": ("$7.4B", "Raised Just In June"),
    },
    {
        "slug": "mahindra-it",
        "content": "content_2026-07-18_ai-won-t-diminish-it-services-will-instead-make-it-more-vita.json",
        "cover_bg": OUT.parent / "covers" / "mahindra-itservices.png",
        "backstory_bg": OUT.parent / "covers" / "mahindra-itservices-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "Mahindra: AI Won't **Kill IT Services**",
            "slide2_headline": "The Fear AI Would **Gut IT Jobs**",
            "slide3_headline": "Mahindra Says AI Is **an Opportunity**",
            "slide4_headline": "Big Stakes for **Jobs and Strategy**",
            "slide5_headline": (
                "Mahindra says AI will make IT services more important, not less. Can "
                "India's IT giants actually reinvent themselves fast enough, or is this "
                "just **AGM optimism**?"
            ),
        },
        "stat": ("5M+", "IT Jobs In India"),
    },
    {
        "slug": "armory",
        "content": "content_2026-07-18_armory-first-built-a-counter-drone-system-in-six-months-and-.json",
        "cover_bg": OUT.parent / "covers" / "armory-drone.png",
        "backstory_bg": OUT.parent / "covers" / "armory-drone-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "2-Year-Old Startup Lands **₹100 Crore Defence Order**",
            "slide2_headline": "A Border Crisis **Nobody Solved Fast Enough**",
            "slide3_headline": "**₹100 Crore** MoD Order for SURGE",
            "slide4_headline": "What This Means for **Defence Startups**",
            "slide5_headline": (
                "Should the Ministry of Defence fast-track startups like Armory, or is "
                "moving fast on **national security too risky**?"
            ),
        },
        "stat": ("5 km", "Drone Detection Range"),
    },
    {
        "slug": "kimi",
        "content": "content_2026-07-18_china-s-kimi-k3-rattles-us-ai-industry.json",
        "cover_bg": OUT.parent / "covers" / "kimi-lab.png",
        "backstory_bg": OUT.parent / "covers" / "kimi-lab-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "China's Kimi Just **Dethroned America's Best AI**",
            "slide2_headline": "From Zero to **China's Hottest AI Lab**",
            "slide3_headline": "Kimi K3: **World's Largest** Open AI Model",
            "slide4_headline": "The **Price-Performance Gap** Is Gone",
            "slide5_headline": (
                "If a Chinese open AI is #1 at coding and costs 5x less, why would any "
                "startup still pay **for OpenAI or Anthropic**?"
            ),
        },
        "news_stat": ("2.8T", "Parameters, Largest Open Model"),
        "stat": ("5x", "Cheaper Than Claude"),
    },
    {
        "slug": "fedex-raj",
        "content": "content_2026-07-18_how-a-missed-roommate-interview-helped-raj-subramaniam-begin.json",
        "cover_bg": OUT.parent / "covers" / "fedex-tarmac.png",
        "backstory_bg": OUT.parent / "covers" / "fedex-tarmac-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "One Phone Call. Thirty Years. **FedEx CEO.**",
            "slide2_headline": "IIT Grad With **No Job Offer**",
            "slide3_headline": "Roommate Said No. **Raj Said Yes.**",
            "slide4_headline": "One Seized Moment Built **a Global Empire**",
            "slide5_headline": (
                "Raj had IIT and two US degrees, and still almost missed his shot. Is the "
                "real skill credentials, or **the courage to chase your own opportunity**?"
            ),
        },
        "timeline": [
            {"year": "1991", "text": "Raj grabs his roommate's FedEx interview slot"},
            {"year": "1991", "text": "He lands the job in Memphis"},
            {"year": "2022", "text": "Raj becomes only FedEx's second-ever CEO"},
            {"year": "2026", "text": "FedEx stock is up 102% since he took over", "accent": True},
        ],
        "stat": ("500K+", "Employees Across 220+ Countries"),
    },
    {
        "slug": "rbi-plastic-notes",
        "content": "content_2026-07-18_it-s-a-revamp-rbi-steps-ahead-on-plan-for-plastic-rupee-note.json",
        "cover_bg": OUT.parent / "covers" / "rbi-rupee.png",
        "backstory_bg": OUT.parent / "covers" / "rbi-rupee-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "India's Paper Rupee Era **May Be Over**",
            "slide2_headline": "India Tried This Before, **and Quit**",
            "slide3_headline": "RBI's Print Arm Is **Calling Suppliers**",
            "slide4_headline": "Cheaper, Tougher, **Harder to Fake**",
            "slide5_headline": (
                "India still runs on cash, with currency at 12.1% of GDP. But if your ₹10 "
                "note can survive a wash, would that **change how you use money**?"
            ),
        },
        "stat": ("2.5x", "Longer-Lasting Than Paper"),
    },
    {
        "slug": "jio-financial",
        "content": "content_2026-07-18_jio-financial-services-share-price-jumps-6-after-q1-profit-s.json",
        "cover_bg": OUT.parent / "covers" / "mumbai-skyline.png",
        "backstory_bg": OUT.parent / "covers" / "mumbai-skyline-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "Jio Financial's Profit Jumped **156%**",
            "slide2_headline": "The Demerger That **Struggled to Prove Itself**",
            "slide3_headline": "Profit Hits **Rs 830 Crore**, Up 156%",
            "slide4_headline": "Brokerages Turn **Bullish** Despite Cost Worries",
            "slide5_headline": (
                "Has Jio Financial finally proven its lending and payments bet, or is "
                "**one strong quarter not enough**?"
            ),
        },
        "chart": [
            {"value": 324, "display": "₹324 Cr"},
            {"value": 830, "display": "₹830 Cr", "accent": True},
        ],
        "stat": ("25M+", "JioFinance App Users"),
    },
    {
        "slug": "jio-ipo-marketing",
        "content": "content_2026-07-18_jio-likely-to-begin-ipo-marketing-from-next-week-for-india-s.json",
        "cover_bg": OUT.parent / "covers" / "trading-floor.png",
        "backstory_bg": OUT.parent / "covers" / "trading-floor-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "India's **Biggest IPO** Starts Selling",
            "slide2_headline": "**Seven Years** In The Making",
            "slide3_headline": "Soft Marketing Begins **Before Roadshows**",
            "slide4_headline": "Why It Could **Shake Up Markets**",
            "slide5_headline": (
                "Jio's IPO is finally here after seven years. Are you buying the hype, or "
                "**waiting for the price band**?"
            ),
        },
        "news_stat": ("₹40,000 Cr", "Potential IPO Fundraise"),
        "stat": ("$180B", "Bankers' Top Valuation Estimate"),
    },
    {
        "slug": "jsw-steel",
        "content": "content_2026-07-18_jsw-steel-s-profit-doubles-on-revenue-growth-beats-estimates.json",
        "cover_bg": OUT.parent / "covers" / "steel-mill.png",
        "backstory_bg": OUT.parent / "covers" / "steel-mill-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "JSW Steel's Profit **Just Doubled**",
            "slide2_headline": "India's Steel Giant Was **Fighting Weak Prices**",
            "slide3_headline": "Profit More Than Doubles, **Crushes Estimates**",
            "slide4_headline": "A Steel Beat That Signals **Broader Demand**",
            "slide5_headline": (
                "JSW Steel beat estimates by over ₹1,100 crore while still spending big on "
                "expansion. Is this the start of a **steel supercycle in India**, or just a "
                "one quarter blip?"
            ),
        },
        "chart": [
            {"value": 2209, "display": "₹2,209 Cr"},
            {"value": 4696, "display": "₹4,696 Cr", "accent": True},
        ],
        "stat": ("₹47,364 Cr", "Quarterly Revenue"),
    },
    {
        "slug": "makemytrip-ipo",
        "content": "content_2026-07-18_makemytrip-ipo-soon-online-travel-giant-files-confidential-d.json",
        "cover_bg": OUT.parent / "covers" / "airport-lounge.png",
        "backstory_bg": OUT.parent / "covers" / "airport-lounge-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "India's Top Travel App **Comes Home**",
            "slide2_headline": "Built For India, **Listed In America**",
            "slide3_headline": "MakeMyTrip Files DRHP For **$1B IPO**",
            "slide4_headline": "A Homecoming With **Real Stakes** For Everyone",
            "slide5_headline": (
                "MakeMyTrip chose America over India back in 2010. Should Indian startups "
                "list at home from day one, or does a **Nasdaq listing still open more "
                "doors**?"
            ),
        },
        "timeline": [
            {"year": "2000", "text": "MakeMyTrip is founded in India"},
            {"year": "2010", "text": "Lists on Nasdaq, raising $80.5 million"},
            {"year": "2026", "text": "Files DRHP for a $1 billion India IPO", "accent": True},
        ],
        "stat": ("₹8,600 Cr", "Potential IPO Size"),
    },
    {
        "slug": "manipal-hospitals",
        "content": "content_2026-07-18_manipal-hospitals-is-said-to-cut-ipo-valuation-from-10-12-bi.json",
        "cover_bg": OUT.parent / "covers" / "hospital-lobby.png",
        "backstory_bg": OUT.parent / "covers" / "hospital-lobby-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "India's biggest hospital IPO **just got cheaper**",
            "slide2_headline": "From one medical college to **38 hospitals**",
            "slide3_headline": "Valuation cut to **$8.3 billion** amid volatility",
            "slide4_headline": "Still India's **biggest listing** of the year",
            "slide5_headline": (
                "Is an $8.3 billion valuation still too rich for a hospital chain, or a "
                "**bargain after the cut**?"
            ),
        },
        "chart": [
            {"value": 11, "display": "$11B"},
            {"value": 8.3, "display": "$8.3B", "accent": True},
        ],
        "stat": ("10,700+", "Hospital Beds"),
    },
    {
        "slug": "hydrogen-train",
        "content": "content_2026-07-18_pm-narendra-modi-launches-india-s-first-hydrogen-train-what-.json",
        "cover_bg": OUT.parent / "covers" / "hydrogen-train.png",
        "backstory_bg": OUT.parent / "covers" / "hydrogen-train-legacy.png",
        "logo": None,
        "headlines": {
            "slide1_label": "India's First Hydrogen Train **Just Changed History**",
            "slide2_headline": "India's Rail Was **Nearly All Green**",
            "slide3_headline": "NaMo Green Rail Is **Now Officially Running**",
            "slide4_headline": "Historic Milestone, But **Real Tests Ahead**",
            "slide5_headline": (
                "India built the train body but imports the fuel cell, its core engine. Is "
                "this really 'Make in India', or are we calling **a stepping stone the "
                "finish line**?"
            ),
        },
        "stat": ("35", "More Hydrogen Trains Planned"),
    },
    {
        "slug": "reliance-jio-q1",
        "content": "content_2026-07-18_reliance-jio-q1-results-ipo-bound-telco-s-net-profit-rises-9.json",
        "cover_bg": OUT.parent / "covers" / "telecom-tower.png",
        "backstory_bg": OUT.parent / "covers" / "telecom-tower-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "Jio's Profit Rises 9% **Before Its IPO**",
            "slide2_headline": "From Rs250/GB To **India's Broadband King**",
            "slide3_headline": "Profit Up 9%, ARPU Climbs To **Rs215.6**",
            "slide4_headline": "Numbers That Matter For **The IPO Pitch**",
            "slide5_headline": (
                "Jio wants to be valued as a tech company, not just a telecom operator, "
                "ahead of its IPO. Do these numbers back that up, or is it **still just a "
                "phone company**?"
            ),
        },
        "chart": [
            {"value": 7112, "display": "₹7,112 Cr"},
            {"value": 7764, "display": "₹7,764 Cr", "accent": True},
        ],
        "stat": ("533.3M", "Total Jio Users"),
    },
    {
        "slug": "reliance-retail-q1",
        "content": "content_2026-07-18_reliance-retail-q1-results-quick-commerce-spends-drag-pat-14.json",
        "cover_bg": OUT.parent / "covers" / "delivery-rider.png",
        "backstory_bg": OUT.parent / "covers" / "delivery-rider-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "Reliance Profit Drops 14% **On Quick Commerce**",
            "slide2_headline": "JioMart's **Rocky Road** To Quick Commerce",
            "slide3_headline": "Q1 FY27: Revenue Up, **Profit Down 14%**",
            "slide4_headline": "The Bet: **Trade Margin For Market Share**",
            "slide5_headline": (
                "Reliance is taking a 14% profit hit to chase quick commerce share from "
                "Blinkit and Zepto. Smart long game, or **margin bleed that never stops**?"
            ),
        },
        "chart": [
            {"value": 3271, "display": "₹3,271 Cr"},
            {"value": 2806, "display": "₹2,806 Cr", "accent": True},
        ],
        "stat": ("252", "New Stores Added This Quarter"),
    },
    {
        "slug": "ril-q1",
        "content": "content_2026-07-18_ril-q1-results-revenue-up-25-yoy-to-rs-3-11-lakh-crore-profi.json",
        "cover_bg": OUT.parent / "covers" / "oil-refinery.png",
        "backstory_bg": OUT.parent / "covers" / "oil-refinery-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "RIL Just Crossed **₹3 Lakh Crore Revenue**",
            "slide2_headline": "From Oil Refiner to **India's Everything Company**",
            "slide3_headline": "Revenue Hits **₹3 Lakh Crore** First Time",
            "slide4_headline": "Three Big Things **To Watch Next**",
            "slide5_headline": (
                "Jio's IPO could value it at $170 billion. Would you buy in, or is that "
                "**too pricey**?"
            ),
        },
        "chart": [
            {"value": 2.49, "display": "₹2.49L Cr"},
            {"value": 3.11, "display": "₹3.11L Cr", "accent": True},
        ],
        "stat": ("₹54,067 Cr", "EBITDA, Up 10%"),
    },
    {
        "slug": "skyroot",
        "content": "content_2026-07-18_spacetech-unicorn-skyroot-launches-vikram-1-marks-india-s-fi.json",
        "cover_bg": OUT.parent / "covers" / "skyroot.png",
        "backstory_bg": OUT.parent / "covers" / "skyroot-cleanroom.png",
        "logo": None,
        "headlines": {
            "slide1_label": "India's First Private Rocket **Just Reached Orbit**",
            "slide2_headline": "For Decades, **Only ISRO** Could Launch Rockets",
            "slide3_headline": "Vikram-1 Lifts Off, **All Four Stages Succeed**",
            "slide4_headline": "India's Commercial Space Race **Just Sped Up**",
            "slide5_headline": "Should ISRO feel **threatened, or proud**?",
        },
        "timeline": [
            {"year": "2018", "text": "Ex-ISRO engineers found Skyroot Aerospace"},
            {"year": "2020", "text": "India opens the space sector to private firms"},
            {"year": "2022", "text": "Skyroot reaches space on a test flight"},
            {"year": "2026", "text": "Vikram-1 becomes India's first private orbital launch", "accent": True},
        ],
        "stat": ("450 km", "Orbital Altitude Reached"),
    },
    {
        "slug": "copper",
        "content": "content_2026-07-18_the-new-oil-why-the-world-is-chasing-copper.json",
        "cover_bg": OUT.parent / "covers" / "copper-coils.png",
        "backstory_bg": OUT.parent / "covers" / "copper-coils-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "Copper Is **the New Oil**. Here's Why.",
            "slide2_headline": "Copper Was Always Important. **Now It's Critical.**",
            "slide3_headline": "Demand Is Surging. **Supply Cannot Keep Up.**",
            "slide4_headline": "No Copper Means **No Clean Energy**",
            "slide5_headline": (
                "India imports over half its copper but has untapped reserves at home. "
                "Should we mine them, even with **environmental costs**?"
            ),
        },
        "news_stat": ("30%", "Supply Shortfall By 2035"),
        "stat": ("550K", "Tonnes AI Data Centers May Need by 2030"),
    },
    {
        "slug": "china-investment-policy",
        "content": "content_2026-07-18_us-less-reliable-india-may-need-to-open-the-door-wider-to-th.json",
        "cover_bg": OUT.parent / "covers" / "container-port.png",
        "backstory_bg": OUT.parent / "covers" / "container-port-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "Modi's own adviser: **let China in more**",
            "slide2_headline": "India **shut its China door** in 2020",
            "slide3_headline": "PMEAC's Rakesh Mohan urges **Chinese investment push**",
            "slide4_headline": "A potential shift in **India's China strategy**",
            "slide5_headline": (
                "Should India ease its China investment rules to boost manufacturing, or "
                "is that **too risky after 2020**?"
            ),
        },
    },
    {
        "slug": "us-tariffs-bill",
        "content": "content_2026-07-18_us-senate-bill-seeks-100-tariffs-on-india-4-other-nations-fo.json",
        "cover_bg": OUT.parent / "covers" / "us-capitol.png",
        "backstory_bg": OUT.parent / "covers" / "us-capitol-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "US Senate wants **100% tariffs** on India",
            "slide2_headline": "India kept buying **discounted Russian crude**",
            "slide3_headline": "Bipartisan bill targets **India, China**, three others",
            "slide4_headline": "Tariffs as **a geopolitical weapon**, first time",
            "slide5_headline": (
                "Should India keep buying discounted Russian oil even if it risks "
                "**100% US tariffs**?"
            ),
        },
    },
    {
        "slug": "chip-bear-market",
        "content": "content_2026-07-18_wall-street-s-chip-index-enters-bear-market-is-the-ai-bubble.json",
        "cover_bg": OUT.parent / "covers" / "chip-ticker.png",
        "backstory_bg": OUT.parent / "covers" / "chip-ticker-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "China just **crashed the AI chip party**",
            "slide2_headline": "The **Biggest Chip Rally** in History",
            "slide3_headline": "Moonshot's Kimi K3 **Sparks a Repeat**",
            "slide4_headline": "The AI Spending Story **Is Changing**",
            "slide5_headline": (
                "DeepSeek spooked markets in January 2025, and stocks bounced back in "
                "weeks. Is Kimi K3 different, or will **this selloff reverse too**?"
            ),
        },
        "timeline": [
            {"year": "Mar 2026", "text": "Chip stocks begin a historic rally"},
            {"year": "Jun 2026", "text": "The rally peaks, stocks up 105%"},
            {"year": "Jul 2026", "text": "Kimi K3 launch triggers a 20% crash, $3.3T gone", "accent": True},
        ],
        "stat": ("$3.3T", "Wiped From Chip Stocks"),
    },
    {
        "slug": "yes-bank",
        "content": "content_2026-07-18_yes-bank-q1-results-net-profit-surges-34-yoy-to-rs-1-071-cro.json",
        "cover_bg": OUT.parent / "covers" / "bank-branch.png",
        "backstory_bg": OUT.parent / "covers" / "bank-branch-backstory.png",
        "logo": None,
        "headlines": {
            "slide1_label": "Yes Bank Is Back. **Numbers Prove It.**",
            "slide2_headline": "From ₹370 Stock to **₹50,000 Withdrawal Cap**",
            "slide3_headline": "**34% Profit Jump.** Ratings Upgraded. Margins Hold.",
            "slide4_headline": "This Turnaround Changes **What's Possible Next**",
            "slide5_headline": (
                "SBI and other Indian banks bailed out Yes Bank in 2020, and now a "
                "Japanese bank is its biggest shareholder. Is that proof India's banking "
                "system is maturing, or did the rescue just **hand a prize asset to "
                "foreign capital**?"
            ),
        },
        "timeline": [
            {"year": "2018", "text": "Yes Bank stock hits ₹370, India's hottest bank"},
            {"year": "2020", "text": "RBI caps withdrawals at ₹50,000 amid crisis"},
            {"year": "2020", "text": "SBI leads a ₹10,000 crore bailout"},
            {"year": "2026", "text": "Profit jumps 34% to ₹1,071 crore", "accent": True},
        ],
        "stat": ("24%", "Stake Now Owned By Japan's SMBC"),
    },
]


def render_story(cfg):
    data = json.loads((CONTENT_DIR / cfg["content"]).read_text())
    s = data["slides"]
    slug = cfg["slug"]
    story_out = OUT / slug
    h = cfg["headlines"]
    b = BODIES.get(slug, {})
    jobs = []

    inner, css, autofit = cover_slide(
        headline=h["slide1_label"],
        subhead=s["slide1_hook"]["subhead"],
        bg_src=cfg["cover_bg"],
        logo_src=cfg.get("logo"),
        badge_num=1,
    )
    jobs.append((inner, css, story_out / f"{slug}-cover.png", autofit))

    inner, css, autofit = backstory_slide(
        label=s["slide2_backstory"]["label"],
        headline=h["slide2_headline"],
        body=b.get("slide2_body", s["slide2_backstory"]["body"]),
        bg_src=cfg["backstory_bg"],
        badge_num=2,
    )
    jobs.append((inner, css, story_out / f"{slug}-backstory.png", autofit))

    inner, css, autofit = news_slide(
        label=s["slide3_news"]["label"],
        headline=h["slide3_headline"],
        body=b.get("slide3_body", s["slide3_news"]["body"]),
        badge_num=3,
        chart=cfg.get("chart"),
        chart_annotate=cfg.get("chart_annotate", True),
        timeline=cfg.get("timeline"),
        stat=cfg.get("news_stat"),
    )
    jobs.append((inner, css, story_out / f"{slug}-news.png", autofit))

    inner, css, autofit = why_slide(
        label=s["slide4_why"]["label"],
        headline=h["slide4_headline"],
        bullets=b.get("slide4_bullets", s["slide4_why"]["bullets"]),
        badge_num=4,
        stat=cfg.get("stat"),
    )
    jobs.append((inner, css, story_out / f"{slug}-why.png", autofit))

    inner, css, autofit = engage_slide(
        label=s["slide5_engage"]["label"],
        headline=b.get("slide5_headline", h["slide5_headline"]),
        cta=s["slide5_engage"]["cta"],
        badge_num=5,
    )
    jobs.append((inner, css, story_out / f"{slug}-engage.png", autofit))

    for inner, css, out_path, autofit in jobs:
        render_to_png(inner, css, out_path, autofit=autofit)
        print(f"-> {out_path}")


if __name__ == "__main__":
    import sys

    only = set(sys.argv[1:]) or None
    for cfg in STORIES:
        if only and cfg["slug"] not in only:
            continue
        print(f"=== {cfg['slug']} ===")
        render_story(cfg)
    print("done")
