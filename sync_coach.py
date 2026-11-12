import os
from datetime import datetime
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
ROOT_PAGE_ID = os.getenv("NOTION_PAGE_ID")
OUTPUT_FILE = os.path.join("output", "skills.md")

if not NOTION_TOKEN or not ROOT_PAGE_ID:
    raise ValueError("Erreur : NOTION_TOKEN et NOTION_PAGE_ID doivent être définis dans le fichier .env")

notion = Client(auth=NOTION_TOKEN)


def extract_rich_text(rich_text_list):
    """Extrait le texte brut d'une liste rich_text Notion en conservant le formatage de base."""
    result = ""
    for item in rich_text_list:
        text = item.get("plain_text", "")
        annotations = item.get("annotations", {})
        if annotations.get("code"):
            text = f"`{text}`"
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        href = item.get("href")
        if href:
            text = f"[{text}]({href})"
        result += text
    return result


def extract_property_value(prop):
    """Extrait la valeur lisible d'une propriété de base de données Notion."""
    p_type = prop.get("type")
    if p_type == "title":
        return extract_rich_text(prop.get("title", []))
    elif p_type == "rich_text":
        return extract_rich_text(prop.get("rich_text", []))
    elif p_type == "select":
        sel = prop.get("select")
        return sel.get("name", "") if sel else ""
    elif p_type == "multi_select":
        return ", ".join([s.get("name", "") for s in prop.get("multi_select", [])])
    elif p_type == "number":
        val = prop.get("number")
        return str(val) if val is not None else ""
    elif p_type == "checkbox":
        return "Oui" if prop.get("checkbox") else "Non"
    elif p_type == "date":
        d = prop.get("date")
        return d.get("start", "") if d else ""
    elif p_type == "url":
        return prop.get("url") or ""
    return ""


def database_to_markdown(database_id):
    """Convertit une base de données Notion en tableau Markdown."""
    rows = []
    has_more = True
    start_cursor = None

    while has_more:
        response = notion.databases.query(
            database_id=database_id,
            start_cursor=start_cursor
        )
        rows.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    if not rows:
        return "*Base de données vide.*
"

    # Récupérer les colonnes depuis la première ligne (en mettant le titre en premier)
    sample_props = rows[0].get("properties", {})
    title_cols = [k for k, v in sample_props.items() if v.get("type") == "title"]
    other_cols = [k for k, v in sample_props.items() if v.get("type") != "title"]
    headers = title_cols + other_cols

    md_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |"
    ]

    for row in rows:
        props = row.get("properties", {})
        values = [extract_property_value(props.get(col, {})).replace("
", " ") for col in headers]
        md_lines.append("| " + " | ".join(values) + " |")

    return "
" + "
".join(md_lines) + "

"


def block_to_markdown(block, indent=0):
    """Convertit un bloc Notion en Markdown."""
    b_type = block.get("type")
    prefix = "  " * indent

    if b_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "to_do", "quote", "callout"]:
        text = extract_rich_text(block[b_type].get("rich_text", []))
        if not text and b_type == "paragraph":
            return "
"
        if b_type == "heading_1":
            return f"
# {text}
"
        elif b_type == "heading_2":
            return f"
## {text}
"
        elif b_type == "heading_3":
            return f"
### {text}
"
        elif b_type == "bulleted_list_item":
            return f"{prefix}- {text}
"
        elif b_type == "numbered_list_item":
            return f"{prefix}1. {text}
"
        elif b_type == "to_do":
            checked = "x" if block[b_type].get("checked") else " "
            return f"{prefix}- [{checked}] {text}
"
        elif b_type == "quote":
            return f"{prefix}> {text}
"
        elif b_type == "callout":
            icon = block[b_type].get("icon", {}).get("emoji", "💡")
            return f"
> {icon} **{text}**
"
        else:
            return f"{prefix}{text}
"
    elif b_type == "divider":
        return "
---
"
    elif b_type == "code":
        lang = block["code"].get("language", "")
        code_text = extract_rich_text(block["code"].get("rich_text", []))
        return f"
```{lang}
{code_text}
```
"

    return ""


def fetch_blocks_recursive(block_id, depth=0, indent=0):
    """Parcourt récursivement tous les blocs, sous-pages et bases de données."""
    markdown_output = ""
    has_more = True
    start_cursor = None

    while has_more:
        response = notion.blocks.children.list(
            block_id=block_id,
            start_cursor=start_cursor
        )
        blocks = response.get("results", [])

        for block in blocks:
            b_type = block.get("type")

            if b_type == "child_page":
                title = block["child_page"].get("title", "Sans titre")
                heading_level = "#" * min(depth + 2, 6)
                markdown_output += f"
{heading_level} {title}
"
                markdown_output += fetch_blocks_recursive(block["id"], depth=depth + 1, indent=0)

            elif b_type == "child_database":
                title = block["child_database"].get("title", "Base de données")
                heading_level = "#" * min(depth + 2, 6)
                markdown_output += f"
{heading_level} {title}
"
                markdown_output += database_to_markdown(block["id"])

            else:
                markdown_output += block_to_markdown(block, indent=indent)
                if block.get("has_children"):
                    next_indent = indent + 1 if b_type in ["bulleted_list_item", "numbered_list_item", "to_do"] else indent
                    markdown_output += fetch_blocks_recursive(block["id"], depth=depth, indent=next_indent)

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return markdown_output


def generate_skill_file():
    print("🔄 Synchronisation des connaissances badminton depuis Notion...")
    knowledge_base = fetch_blocks_recursive(ROOT_PAGE_ID)
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")

    skill_header = f"""---
name: badminton-super-coach
description: Coach expert en badminton (technique, tactique, physique et mental) s'appuyant sur la base de connaissances Notion de l'utilisateur.
last_synced: "{last_updated}"
---

# Rôle et Posture du Coach
Tu es un entraîneur de badminton de haut niveau. Tu analyses les demandes du joueur, conçois des séances d'entraînement structurées, corriges les défauts techniques et élabores des plans tactiques (simple, double, mixte) en t'appuyant **prioritairement et rigoureusement** sur la base de connaissances ci-dessous.

## Règles de coaching :
- Sois précis, exigeant, structuré et pédagogique.
- Cite les principes, exercices ou schémas tactiques issus de la base de connaissances dès qu'ils s'appliquent.
- Si une information n'est pas présente dans la base ci-dessous, indique-le brièvement avant de compléter avec ton expertise générale du badminton.

---

# Base de Connaissances Badminton (Source : Notion)
"""

    os.makedirs("output", exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.write(skill_header + knowledge_base)

    print(f"✅ Fichier '{OUTPUT_FILE}' généré avec succès ({last_updated}) !")


if __name__ == "__main__":
    generate_skill_file()
