import os
from datetime import datetime
from notion_client import Client
from notion_client.errors import APIResponseError
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "").strip()
PAGE_IDS = os.getenv("NOTION_PAGE_IDS", "").strip() or os.getenv("NOTION_PAGE_ID", "").strip()
ROOT_IDS = [page_id.replace("-", "").strip() for page_id in PAGE_IDS.split(",") if page_id.strip()]
OUTPUT_FILE = os.path.join("output", "skills.md")

if not NOTION_TOKEN or not ROOT_IDS:
    raise ValueError("Erreur : NOTION_TOKEN et NOTION_PAGE_IDS doivent être définis.")

notion = Client(auth=NOTION_TOKEN)
visited_ids = set()


def extract_rich_text(rich_text_list):
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
    elif p_type == "status":
        st = prop.get("status")
        return st.get("name", "") if st else ""
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


def query_database_rows(database_id):
    """Interroge une base de données Notion (compatible notion-client >= 2.3 / API 2025-09-03)."""
    rows = []
    has_more = True
    start_cursor = None

    data_source_id = None
    try:
        db_info = notion.databases.retrieve(database_id=database_id)
        data_sources = db_info.get("data_sources", [])
        if data_sources:
            data_source_id = data_sources[0].get("id")
    except Exception:
        pass

    while has_more:
        body = {"start_cursor": start_cursor} if start_cursor else {}

        if data_source_id and hasattr(notion, "data_sources"):
            response = notion.data_sources.query(data_source_id=data_source_id, **body)
        elif hasattr(notion.databases, "query"):
            response = notion.databases.query(database_id=database_id, **body)
        else:
            response = notion.request(
                path=f"databases/{database_id}/query",
                method="POST",
                body=body
            )

        rows.extend(response.get("results", []))
        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return rows


def database_to_markdown(database_id, depth=0):
    """Convertit une base de données Notion en tableau Markdown ET lit le contenu interne de chaque fiche."""
    print(f"📊 Lecture de la base de données : {database_id}")
    rows = query_database_rows(database_id)

    print(f"   -> {len(rows)} entrées trouvées dans la base de données.")
    if not rows:
        return "*Base de données vide.*\n"

    sample_props = rows[0].get("properties", {})
    title_cols = [k for k, v in sample_props.items() if v.get("type") == "title"]
    other_cols = [k for k, v in sample_props.items() if v.get("type") != "title"]
    headers = title_cols + other_cols

    md_lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join(["---"] * len(headers)) + " |"
    ]

    details_md = ""
    for row in rows:
        props = row.get("properties", {})
        values = [extract_property_value(props.get(col, {})).replace("\n", " ") for col in headers]
        md_lines.append("| " + " | ".join(values) + " |")

        row_title = values[0] if values else "Fiche"
        row_content = fetch_blocks_recursive(row["id"], depth=depth + 1)
        if row_content.strip():
            heading_level = "#" * min(depth + 3, 6)
            details_md += f"\n{heading_level} Détails : {row_title}\n{row_content}"

    return "\n" + "\n".join(md_lines) + "\n" + details_md + "\n"


def block_to_markdown(block, indent=0):
    b_type = block.get("type")
    prefix = "  " * indent

    if b_type in ["paragraph", "heading_1", "heading_2", "heading_3", "bulleted_list_item", "numbered_list_item", "to_do", "quote", "callout", "toggle"]:
        text = extract_rich_text(block[b_type].get("rich_text", []))
        if not text and b_type == "paragraph":
            return "\n"
        if b_type == "heading_1":
            return f"\n# {text}\n"
        elif b_type == "heading_2":
            return f"\n## {text}\n"
        elif b_type == "heading_3":
            return f"\n### {text}\n"
        elif b_type == "bulleted_list_item":
            return f"{prefix}- {text}\n"
        elif b_type == "numbered_list_item":
            return f"{prefix}1. {text}\n"
        elif b_type == "to_do":
            checked = "x" if block[b_type].get("checked") else " "
            return f"{prefix}- [{checked}] {text}\n"
        elif b_type == "quote":
            return f"{prefix}> {text}\n"
        elif b_type == "callout":
            icon = block[b_type].get("icon", {}).get("emoji", "💡")
            return f"\n> {icon} **{text}**\n"
        elif b_type == "toggle":
            return f"\n**▸ {text}**\n"
        else:
            return f"{prefix}{text}\n"
    elif b_type == "divider":
        return "\n---\n"
    elif b_type == "code":
        lang = block["code"].get("language", "")
        code_text = extract_rich_text(block["code"].get("rich_text", []))
        return f"\n```{lang}\n{code_text}\n```\n"

    return ""


def fetch_blocks_recursive(block_id, depth=0, indent=0):
    clean_id = block_id.replace("-", "")
    if clean_id in visited_ids:
        return ""
    visited_ids.add(clean_id)

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
                print(f"📄 Sous-page trouvée : {title}")
                heading_level = "#" * min(depth + 2, 6)
                markdown_output += f"\n{heading_level} {title}\n"
                markdown_output += fetch_blocks_recursive(block["id"], depth=depth + 1, indent=0)

            elif b_type == "child_database":
                title = block["child_database"].get("title", "Base de données")
                print(f"🗄️ Base de données trouvée : {title}")
                heading_level = "#" * min(depth + 2, 6)
                markdown_output += f"\n{heading_level} {title}\n"
                try:
                    markdown_output += database_to_markdown(block["id"], depth=depth)
                except Exception as e:
                    print(f"⚠️ Impossible de lire la base '{title}' (probablement une vue liée) : {e}")
                    markdown_output += f"*Base de données liée ({title}) non exportable directement.*\n"

            elif b_type == "link_to_page":
                link_info = block.get("link_to_page", {})
                target_id = link_info.get("page_id") or link_info.get("database_id")
                if target_id:
                    print(f"🔗 Lien vers page/base détecté : {target_id}")
                    markdown_output += extract_any_target(target_id, depth=depth + 1)

            elif b_type == "synced_block":
                synced_from = block.get("synced_block", {}).get("synced_from")
                target_id = synced_from["block_id"] if synced_from else block["id"]
                markdown_output += fetch_blocks_recursive(target_id, depth=depth, indent=indent)

            else:
                markdown_output += block_to_markdown(block, indent=indent)
                if block.get("has_children"):
                    next_indent = indent + 1 if b_type in ["bulleted_list_item", "numbered_list_item", "to_do", "toggle"] else indent
                    markdown_output += fetch_blocks_recursive(block["id"], depth=depth, indent=next_indent)

        has_more = response.get("has_more", False)
        start_cursor = response.get("next_cursor")

    return markdown_output


def extract_any_target(target_id, depth=0):
    """Détecte automatiquement si l'ID est une Page ou une Base de Données."""
    is_page = False
    title = "Page Notion"

    try:
        page = notion.pages.retrieve(page_id=target_id)
        is_page = True
        props = page.get("properties", {})
        for prop in props.values():
            if prop.get("type") == "title":
                title = extract_rich_text(prop.get("title", [])) or title
    except APIResponseError as e:
        if "is a database" not in str(e).lower():
            raise

    if is_page:
        print(f"✅ Cible identifiée comme PAGE : '{title}'")
        content = fetch_blocks_recursive(target_id, depth=depth)
        return f"\n## {title}\n{content}"

    db = notion.databases.retrieve(database_id=target_id)
    title = extract_rich_text(db.get("title", [])) or "Base de données"
    print(f"✅ Cible identifiée comme BASE DE DONNÉES : '{title}'")
    return f"\n## {title}\n" + database_to_markdown(target_id, depth=depth)


def generate_skill_file():
    print(f"🔄 Synchronisation depuis Notion (IDs : {', '.join(ROOT_IDS)})...")
    knowledge_base = "\n".join(extract_any_target(root_id) for root_id in ROOT_IDS)
    last_updated = datetime.now().strftime("%Y-%m-%d %H:%M")

    if not knowledge_base.strip():
        print("⚠️ ATTENTION : Aucun contenu extrait. Vérifiez les logs ci-dessus.")

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

    print(f"✅ Fichier '{OUTPUT_FILE}' généré ({len(knowledge_base)} caractères extraits) !")


if __name__ == "__main__":
    generate_skill_file()