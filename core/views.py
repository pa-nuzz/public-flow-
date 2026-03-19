from django.shortcuts import render

def landing_view(request):

    features = [
    {
        "title": "AI-Powered Sending",
        "description": "Optimize send times, subject lines, and content automatically with machine learning.",
        "icon_svg": """
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
        </svg>
        """
    },
    {
        "title": "Real-Time Analytics",
        "description": "Track opens, clicks, and conversions across every campaign in a clean unified dashboard.",
        "icon_svg": """
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 3v18h18M9 17V9m4 8V5m4 12v-6"/>
        </svg>
        """
    },
    {
        "title": "Bulk Email at Scale",
        "description": "Send millions of personalized emails per day with industry-leading deliverability rates.",
        "icon_svg": """
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16 12H8m8 4H8m8-8H8m12-3H4a2 2 0 00-2 2v14l4-3h14a2 2 0 002-2V7a2 2 0 00-2-2z"/>
        </svg>
        """
    },
    {
        "title": "Inbox Protection",
        "description": "Advanced spam scoring, DKIM/DMARC management, and dedicated IP warming included.",
        "icon_svg": """
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3l7 4v5c0 5-3.5 9-7 9s-7-4-7-9V7l7-4z"/>
        </svg>
        """
    }
]
    
    # Keep testimonial entries realistic and specific so social-proof sections feel trustworthy.
    testimonials = [
    {
        "quote": "We switched from Mailchimp and our inbox delivery rate jumped from 71% to 98.4% in the first two weeks. The AI optimization alone paid for itself in the first campaign.",
        "author": "Aakriti Maharjan",
        "role": "Head of Growth",
        "company": "Forma Labs",
        "initials": "AM",
        "color": "bg-indigo-100 text-indigo-600"
    },
    {
        "quote": "MailexaAI's automation builder is the cleanest I've used. We set up a 12-step onboarding sequence in an afternoon — something that took us weeks with our old provider.",
        "author": "Anuj Paudel",
        "role": "CTO",
        "company": "Stackpath",
        "initials": "AP",
        "color": "bg-green-100 text-green-600"
    },
    {
        "quote": "The analytics dashboard gives us exactly what we need — no clutter, no guesswork. Our team finally agreed on one source of truth for email performance.",
        "author": "Narayan Prasad Ghimire",
        "role": "Marketing Director",
        "company": "Neon Digital",
        "initials": "NG",
        "color": "bg-slate-200 text-slate-600"
    },
    {
        "quote": "We run seasonal campaigns for multiple retail brands. MailexaAI helped us stabilize sender reputation and cut bounce complaints by more than half.",
        "author": "Sujan Khadka",
        "role": "CRM Lead",
        "company": "Orbit Commerce",
        "initials": "SK",
        "color": "bg-violet-100 text-violet-700"
    },
    {
        "quote": "Before this, our team spent hours cleaning lists and checking spam triggers manually. Now pre-send checks are automatic and launches are much faster.",
        "author": "Ritika Basnet",
        "role": "Lifecycle Manager",
        "company": "Northfield SaaS",
        "initials": "RB",
        "color": "bg-emerald-100 text-emerald-700"
    },
    {
        "quote": "The platform made it easy to onboard regional teams with separate sender identities while still keeping central control over standards and limits.",
        "author": "Prabin Adhikari",
        "role": "Operations Director",
        "company": "Aster Mobility",
        "initials": "PA",
        "color": "bg-amber-100 text-amber-700"
    },
    {
        "quote": "We migrated in under a week and saw immediate gains in open reliability. The UI is clean enough that non-technical marketers can ship confidently.",
        "author": "Mina Shrestha",
        "role": "Digital Marketing Manager",
        "company": "Summit Finserve",
        "initials": "MS",
        "color": "bg-rose-100 text-rose-700"
    }
]
    stats = [
    {
        "value": "4.2B+",
        "label": "Emails Delivered",
        "description": "Across all campaigns this year",
        "icon_svg": """
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l9 6 9-6M4 6h16a2 2 0 012 2v8a2 2 0 01-2 2H4a2 2 0 01-2-2V8a2 2 0 012-2z"/>
        </svg>
        """
    },
    {
        "value": "98.7%",
        "label": "Inbox Delivery Rate",
        "description": "Industry-leading placement",
        "icon_svg": """
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 17l6-6 4 4 8-8"/>
        </svg>
        """
    },
    {
        "value": "12,000+",
        "label": "Businesses Onboarded",
        "description": "From startups to enterprises",
        "icon_svg": """
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12h6m-6 4h6M7 4h10a2 2 0 012 2v14l-5-3-5 3V6a2 2 0 012-2z"/>
        </svg>
        """
    },
    {
        "value": "94%",
        "label": "Spam Reduction",
        "description": "vs. previous email providers",
        "icon_svg": """
        <svg xmlns="http://www.w3.org/2000/svg" class="w-5 h-5 text-indigo-600" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 3l7 4v5c0 5-3.5 9-7 9s-7-4-7-9V7l7-4z"/>
        </svg>
        """
    }
]
    plans = [
    {
        "name": "Free",
        "price": "रु 0",
        "yearly_price": "रु 0",
        "period": "forever",
        "description": "Perfect for individuals and small experiments.",
        "badge": None,
        "highlighted": False,
        "features": [
            "500 emails / month",
            "1 sender domain",
            "Basic analytics",
            "Drag-and-drop editor",
            "Community support"
        ],
        "cta": "Get started free"
    },
    {
        "name": "Pro",
        "price": "रु 499",
        "yearly_price": "रु 399/mo",
        "period": "month",
        "description": "For growing teams that need power and deliverability.",
        "badge": "Most popular",
        "highlighted": True,
        "features": [
            "50,000 emails / month",
            "5 sender domains",
            "Advanced analytics & reporting",
            "AI subject line optimization",
            "Visual automation builder",
            "Priority inbox routing",
            "Email & chat support"
        ],
        "cta": "Start Pro trial"
    },
    {
        "name": "Business",
        "price": "रु 1,499",
        "yearly_price": "रु 1,199/mo",
        "period": "month",
        "description": "Enterprise-grade sending for high-volume operations.",
        "badge": None,
        "highlighted": False,
        "features": [
            "500,000 emails / month",
            "Unlimited sender domains",
            "Full analytics suite",
            "AI optimization suite",
            "Advanced automations & flows",
            "Dedicated IP address",
            "Priority SLA support",
            "Custom contracts & billing"
        ],
        "cta": "Contact sales"
    }
]



    return render(request, "landing/index.html", {"features": features, "testimonials": testimonials, "stats": stats, "plans": plans})