#!/usr/bin/env python3
from __future__ import annotations

from collections import defaultdict
from pathlib import Path
import os
import re
import unicodedata

MARKER = "<!-- generated-by: generate_blog.py tags -->"
PROJECT_DIR = Path(__file__).resolve().parent
LEGACY_TAGS_DIR = PROJECT_DIR / "tags"
BLOG_DIR = PROJECT_DIR / "blog"
BLOG_TAGS_DIR = BLOG_DIR / "tags"
SOURCE_POSTS_DIR = BLOG_DIR / "posts"
BLOG_MD_PATH = BLOG_DIR / "blog.md"
LEGACY_BLOG_MD_PATH = PROJECT_DIR / "blog.md"
MYST_YML_PATH = PROJECT_DIR / "myst.yml"
TOC_MARKER_START = "# generated-by: generate_blog.py toc:start"
TOC_MARKER_END = "# generated-by: generate_blog.py toc:end"
BLOG_MARKER_START = "<!-- generated-by: generate_blog.py blog:start -->"
BLOG_MARKER_END = "<!-- generated-by: generate_blog.py blog:end -->"
POST_TAGS_MARKER_START = "<!-- generated-by: generate_blog.py post-tags:start -->"
POST_TAGS_MARKER_END = "<!-- generated-by: generate_blog.py post-tags:end -->"


def strip_quotes(value: str) -> str:
    value = value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1]
    return value


def parse_inline_list(value: str) -> list[str]:
    value = value.strip()
    if not value:
        return []
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [strip_quotes(part) for part in inner.split(",") if part.strip()]
    return [strip_quotes(value)]


def parse_frontmatter(path: Path) -> dict[str, object]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0].strip() != "---":
        return {}

    metadata: dict[str, object] = {}
    active_list: str | None = None

    for line in lines[1:]:
        if line.strip() == "---":
            break

        if active_list:
            item_match = re.match(r"^\s*-\s+(.*)$", line)
            if item_match:
                item = strip_quotes(item_match.group(1))
                if item:
                    metadata.setdefault(active_list, []).append(item)
                continue
            active_list = None

        match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if not match:
            continue

        key, raw_value = match.groups()
        raw_value = raw_value.strip()

        if key == "tags":
            if raw_value:
                metadata[key] = parse_inline_list(raw_value)
            else:
                metadata[key] = []
                active_list = key
            continue

        if key in {"title", "date", "thumbnail"}:
            metadata[key] = strip_quotes(raw_value)

    return metadata


def slugify(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "tag"


def page_slug(path: Path) -> str:
    stem = path.stem
    if not re.match(r"^\d{4}(?:[-_]\d{2})?(?:[-_].*)?$", stem):
        stem = re.sub(r"^\d+[-_ ]+", "", stem)
    normalized = unicodedata.normalize("NFKD", stem)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_text.lower()).strip("-")
    return slug or "page"


def yaml_quote(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def blog_post_route(post_slug: str) -> str:
    return f"/blog/posts/{post_slug}"


def tag_post_route(tag_slug: str, post_slug: str) -> str:
    return f"/blog/tags/{tag_slug}/posts/{post_slug}"


def resolve_asset_path(base_dir: Path, value: str) -> str:
    if not value:
        return ""
    if re.match(r"^[a-z]+://", value):
        return value
    if value.startswith("/"):
        return value
    return Path(os.path.relpath(PROJECT_DIR / value, base_dir)).as_posix()


def split_document(path: Path) -> tuple[list[str], list[str]]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) >= 2 and lines[0].strip() == "---":
        for index, line in enumerate(lines[1:], start=1):
            if line.strip() == "---":
                return lines[: index + 1], lines[index + 1 :]
    return [], lines


def trim_leading_blank_lines(lines: list[str]) -> list[str]:
    index = 0
    while index < len(lines) and not lines[index].strip():
        index += 1
    return lines[index:]


def write_generated_file(path: Path, lines: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def count_indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def find_block_end(lines: list[str], start_index: int) -> int:
    base_indent = count_indent(lines[start_index])
    for index in range(start_index + 1, len(lines)):
        stripped_line = lines[index].strip()
        if stripped_line and not stripped_line.startswith("#") and count_indent(lines[index]) <= base_indent:
            return index
    return len(lines)


def replace_marked_section(
    lines: list[str], start_marker: str, end_marker: str, replacement_lines: list[str]
) -> list[str] | None:
    start_index = None
    end_index = None

    for index, line in enumerate(lines):
        stripped_line = line.strip()
        if stripped_line == start_marker:
            start_index = index
            continue
        if stripped_line == end_marker and start_index is not None:
            end_index = index
            break

    if start_index is None or end_index is None:
        return None

    updated_lines = list(lines)
    updated_lines[start_index : end_index + 1] = replacement_lines
    return updated_lines


def leading_generated_post_tag_line_count(lines: list[str]) -> int:
    first_content_index = next((index for index, line in enumerate(lines) if line.strip()), None)
    if first_content_index is None or lines[first_content_index].strip() != POST_TAGS_MARKER_START:
        return 0

    end_index = next(
        (index for index in range(first_content_index + 1, len(lines)) if lines[index].strip() == POST_TAGS_MARKER_END),
        None,
    )
    if end_index is None:
        return 0

    return len(lines) - len(trim_leading_blank_lines(lines[end_index + 1 :]))


def body_has_tag_links(lines: list[str]) -> bool:
    if any(line.strip() in {POST_TAGS_MARKER_START, POST_TAGS_MARKER_END} for line in lines):
        return True

    leading_lines = [line for line in trim_leading_blank_lines(lines)[:8] if line.strip()]
    return any(re.match(r"^(?:\*\*|__)?Tags:(?:\*\*|__)?\s*", line, re.IGNORECASE) for line in leading_lines)


def build_post_tag_link_lines(post: dict[str, object]) -> list[str]:
    tag_links = [
        f"[{tag_name}]({tag_post_route(slugify(str(tag_name)), str(post['slug']))})"
        for tag_name in post["tag_names"]
    ]
    return [
        POST_TAGS_MARKER_START,
        f"**Tags:** {', '.join(tag_links)}",
        POST_TAGS_MARKER_END,
    ]


def update_source_post_tag_links(post: dict[str, object]) -> None:
    source_path = PROJECT_DIR / str(post["path"])
    frontmatter_lines, body_lines = split_document(source_path)
    tag_link_lines = build_post_tag_link_lines(post)

    updated_body_lines = replace_marked_section(
        body_lines,
        POST_TAGS_MARKER_START,
        POST_TAGS_MARKER_END,
        tag_link_lines,
    )

    if updated_body_lines is None:
        if body_has_tag_links(body_lines):
            return

        trimmed_body_lines = trim_leading_blank_lines(body_lines)
        updated_body_lines = [*tag_link_lines]
        if trimmed_body_lines:
            updated_body_lines.extend(["", *trimmed_body_lines])

    updated_body_lines = trim_leading_blank_lines(updated_body_lines)

    output_lines = list(frontmatter_lines)
    if frontmatter_lines and updated_body_lines:
        output_lines.append("")
    output_lines.extend(updated_body_lines)
    source_path.write_text("\n".join(output_lines) + "\n", encoding="utf-8")


def update_myst_toc(posts_by_tag: dict[str, list[dict[str, object]]], all_posts: list[dict[str, object]]) -> None:
    lines = MYST_YML_PATH.read_text(encoding="utf-8").splitlines()

    project_index = next((index for index, line in enumerate(lines) if re.match(r"^project:\s*$", line)), None)
    if project_index is None:
        raise SystemExit(f"Could not find project block in {MYST_YML_PATH}")

    project_indent = count_indent(lines[project_index])
    project_end = find_block_end(lines, project_index)
    toc_index = next(
        (
            index
            for index in range(project_index + 1, project_end)
            if count_indent(lines[index]) == project_indent + 2 and re.match(r"^\s*toc:\s*$", lines[index])
        ),
        None,
    )

    if toc_index is None:
        toc_lines = [f"{' ' * (project_indent + 2)}toc:"]
        if (PROJECT_DIR / "README.md").exists():
            toc_lines.append(f"{' ' * (project_indent + 4)}- file: README.md")
        toc_lines.extend([
            f"{' ' * (project_indent + 4)}- file: {BLOG_MD_PATH.relative_to(PROJECT_DIR).as_posix()}",
            f"{' ' * (project_indent + 6)}children:",
        ])
        toc_index = project_end
        lines[toc_index:toc_index] = toc_lines

    toc_indent = count_indent(lines[toc_index])
    toc_item_indent = toc_indent + 2
    toc_content_start = toc_index + 1
    toc_content_end = find_block_end(lines, toc_index)

    blog_index = next(
        (
            index
            for index in range(toc_content_start, toc_content_end)
            if count_indent(lines[index]) == toc_item_indent
            and re.match(r"^\s*-\s*file:\s*(?:blog/)?blog\.md\s*$", lines[index])
        ),
        None,
    )

    if blog_index is None:
        readme_index = next(
            (
                index
                for index in range(toc_content_start, toc_content_end)
                if count_indent(lines[index]) == toc_item_indent
                and re.match(r"^\s*-\s*file:\s*README\.md\s*$", lines[index])
            ),
            None,
        )
        insert_at = toc_content_end if readme_index is None else find_block_end(lines, readme_index)
        lines[insert_at:insert_at] = [
            f"{' ' * toc_item_indent}- file: {BLOG_MD_PATH.relative_to(PROJECT_DIR).as_posix()}",
            f"{' ' * (toc_item_indent + 2)}children:",
        ]
        blog_index = insert_at

    blog_indent = count_indent(lines[blog_index])
    lines[blog_index] = f"{' ' * blog_indent}- file: {BLOG_MD_PATH.relative_to(PROJECT_DIR).as_posix()}"
    children_index = None

    blog_end = find_block_end(lines, blog_index)
    for index in range(blog_index + 1, blog_end):
        if count_indent(lines[index]) == blog_indent + 2 and re.match(r"^\s*children:\s*$", lines[index]):
            children_index = index
            break

    if children_index is None:
        children_index = blog_index + 1
        lines[children_index:children_index] = [f"{' ' * (blog_indent + 2)}children:"]

    children_indent = count_indent(lines[children_index])
    child_item_indent = children_indent + 2
    child_content_start = children_index + 1
    child_content_end = find_block_end(lines, children_index)

    marker_start_index = None
    marker_end_index = None
    for index in range(child_content_start, child_content_end):
        stripped_line = lines[index].strip()
        if stripped_line == TOC_MARKER_START:
            marker_start_index = index
        if stripped_line == TOC_MARKER_END:
            marker_end_index = index
            break

    generated_lines = [f"{' ' * child_item_indent}{TOC_MARKER_START}"]

    if all_posts:
        generated_lines.append(f"{' ' * child_item_indent}- title: All Posts")
        generated_lines.append(f"{' ' * (child_item_indent + 2)}children:")
        for post in all_posts:
            generated_lines.append(f"{' ' * (child_item_indent + 2)}- file: blog/posts/{post['slug']}.md")

    for tag_name in sorted(posts_by_tag, key=str.lower):
        tag_slug = slugify(tag_name)
        generated_lines.append(f"{' ' * child_item_indent}- file: blog/tags/{tag_slug}.md")
        generated_lines.append(f"{' ' * (child_item_indent + 2)}children:")
        for post in posts_by_tag[tag_name]:
            generated_lines.append(
                f"{' ' * (child_item_indent + 4)}- file: blog/tags/{tag_slug}/posts/{post['slug']}.md"
            )

    generated_lines.append(f"{' ' * child_item_indent}{TOC_MARKER_END}")

    replace_start = child_content_start if marker_start_index is None else marker_start_index
    replace_end = child_content_end if marker_end_index is None else marker_end_index + 1
    lines[replace_start:replace_end] = generated_lines

    site_index = next((index for index, line in enumerate(lines) if re.match(r"^site:\s*$", line)), None)
    if site_index is None:
        lines.extend([
            "site:",
            "  options:",
            "    folders: true",
        ])
        MYST_YML_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    site_indent = count_indent(lines[site_index])
    options_index = None
    site_end = find_block_end(lines, site_index)
    for index in range(site_index + 1, site_end):
        if count_indent(lines[index]) == site_indent + 2 and re.match(r"^\s*options:\s*$", lines[index]):
            options_index = index
            break

    if options_index is None:
        options_index = site_end
        lines[options_index:options_index] = [
            f"{' ' * (site_indent + 2)}options:",
            f"{' ' * (site_indent + 4)}folders: true",
        ]
        MYST_YML_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return

    options_indent = count_indent(lines[options_index])
    option_item_indent = options_indent + 2
    options_end = find_block_end(lines, options_index)

    folders_index = None
    for index in range(options_index + 1, options_end):
        if re.match(r"^\s*folders:\s*", lines[index]):
            folders_index = index

    folders_line = f"{' ' * option_item_indent}folders: true"
    if folders_index is None:
        lines.insert(options_end, folders_line)
        options_end += 1
    else:
        lines[folders_index] = folders_line

    MYST_YML_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def update_blog_page(posts: list[dict[str, object]]) -> None:
    generated_lines = [
        BLOG_MARKER_START,
        "",
        "::::{grid} 1 1 2 2",
        "",
    ]

    for post in posts:
        generated_lines.append(f":::{{card}} {post['title']}")
        generated_lines.append(f":link: {blog_post_route(post['slug'])}")
        blog_thumbnail = resolve_asset_path(BLOG_MD_PATH.parent, str(post["thumbnail_source"]))
        if blog_thumbnail:
            generated_lines.append(f":header: ![{post['title']} thumbnail]({blog_thumbnail})")
        generated_lines.append("")
        if post["date"]:
            generated_lines.append(str(post["date"]))
        generated_lines.append(":::")
        generated_lines.append("")

    generated_lines.extend([
        "::::",
        "",
        BLOG_MARKER_END,
    ])

    source_path = BLOG_MD_PATH if BLOG_MD_PATH.exists() else None
    if source_path is None and LEGACY_BLOG_MD_PATH.exists():
        source_path = LEGACY_BLOG_MD_PATH

    if source_path is not None:
        source_lines = source_path.read_text(encoding="utf-8").splitlines()
        output_lines = replace_marked_section(source_lines, BLOG_MARKER_START, BLOG_MARKER_END, generated_lines)
        if output_lines is None:
            output_lines = source_lines
    else:
        output_lines = [
            "---",
            "title: Blog",
            "---",
            "",
            *generated_lines,
        ]

    BLOG_MD_PATH.parent.mkdir(parents=True, exist_ok=True)
    BLOG_MD_PATH.write_text("\n".join(output_lines) + "\n", encoding="utf-8")

    if LEGACY_BLOG_MD_PATH.exists():
        legacy_contents = LEGACY_BLOG_MD_PATH.read_text(encoding="utf-8")
        if BLOG_MARKER_START in legacy_contents and BLOG_MARKER_END in legacy_contents:
            LEGACY_BLOG_MD_PATH.unlink()


def build_tag_page_lines(tag_name: str, posts: list[dict[str, object]], output_path: Path) -> list[str]:
    tag_slug = slugify(tag_name)
    lines = [
        "---",
        f"title: {yaml_quote(tag_name)}",
        f"description: {yaml_quote(f'Posts tagged with {tag_name}.')}",
        "---",
        "",
        MARKER,
        "",
        f"Posts tagged with **{tag_name}**.",
        "",
        "::::{grid} 1 1 2 2",
        "",
    ]

    for post in posts:
        lines.append(f":::{{card}} {post['title']}")
        lines.append(f":link: {tag_post_route(tag_slug, post['slug'])}")
        thumbnail = resolve_asset_path(output_path.parent, str(post["thumbnail_source"]))
        if thumbnail:
            lines.append(f":header: ![{post['title']} thumbnail]({thumbnail})")
        lines.append("")
        if post["date"]:
            lines.append(str(post["date"]))
        lines.append(":::")
        lines.append("")

    lines.append("::::")
    lines.append("")
    return lines


def build_post_alias_lines(post: dict[str, object], output_path: Path) -> list[str]:
    lines = list(post["frontmatter_lines"])
    source_path = PROJECT_DIR / str(post["path"])
    _, body_lines = split_document(source_path)
    tag_block_line_count = leading_generated_post_tag_line_count(body_lines)
    include_path = Path(os.path.relpath(source_path, output_path.parent)).as_posix()
    body_start_line = len(post["frontmatter_lines"]) + tag_block_line_count
    tag_link_lines = build_post_tag_link_lines(post)
    lines.extend([
        "",
        tag_link_lines[0],
        tag_link_lines[1],
        "",
        f":::{{include}} {include_path}",
        ":filename: false",
        f":start-line: {body_start_line}",
        ":::",
        "",
        tag_link_lines[2],
    ])
    return lines


def main() -> None:
    if not SOURCE_POSTS_DIR.is_dir():
        raise SystemExit(f"Posts directory not found: {SOURCE_POSTS_DIR}")

    posts_by_tag: dict[str, list[dict[str, object]]] = defaultdict(list)
    all_posts: list[dict[str, object]] = []
    slugs: dict[str, str] = {}

    for post_path in sorted(SOURCE_POSTS_DIR.glob("*.md")):
        frontmatter_lines, _ = split_document(post_path)
        metadata = parse_frontmatter(post_path)
        tag_names = metadata.get("tags", [])
        if not isinstance(tag_names, list) or not tag_names:
            continue

        title = metadata.get("title") or post_path.stem.replace("-", " ").title()
        date = metadata.get("date") or ""
        slug = page_slug(post_path)

        post_record = {
            "title": str(title),
            "date": str(date),
            "path": post_path.relative_to(PROJECT_DIR).as_posix(),
            "slug": slug,
            "tag_names": [str(tag_name).strip() for tag_name in tag_names if str(tag_name).strip()],
            "thumbnail_source": str(metadata.get("thumbnail") or ""),
            "frontmatter_lines": frontmatter_lines,
        }
        all_posts.append(post_record)

        for tag_name in tag_names:
            cleaned_tag = str(tag_name).strip()
            if not cleaned_tag:
                continue

            slug = slugify(cleaned_tag)
            existing = slugs.get(slug)
            if existing and existing != cleaned_tag:
                raise SystemExit(
                    f"Conflicting tag slugs: {existing!r} and {cleaned_tag!r} both map to {slug!r}"
                )
            slugs[slug] = cleaned_tag
            posts_by_tag[cleaned_tag].append(post_record)

    for tag_name, tagged_posts in posts_by_tag.items():
        tagged_posts.sort(key=lambda post: (post["date"], str(post["title"]).lower()), reverse=True)

    all_posts.sort(key=lambda post: (post["date"], str(post["title"]).lower()), reverse=True)

    for post in all_posts:
        update_source_post_tag_links(post)

    generated_files: set[Path] = set()

    for tag_name in sorted(posts_by_tag, key=str.lower):
        slug = slugify(tag_name)
        blog_tag_page = BLOG_TAGS_DIR / f"{slug}.md"
        generated_files.add(blog_tag_page.resolve())
        write_generated_file(blog_tag_page, build_tag_page_lines(tag_name, posts_by_tag[tag_name], blog_tag_page))

        for post in posts_by_tag[tag_name]:
            tag_post_page = BLOG_TAGS_DIR / slug / "posts" / f"{post['slug']}.md"
            generated_files.add(tag_post_page.resolve())
            write_generated_file(tag_post_page, build_post_alias_lines(post, tag_post_page))

    for directory in (LEGACY_TAGS_DIR, BLOG_TAGS_DIR):
        if not directory.exists():
            continue
        for file_path in directory.rglob("*.md"):
            resolved_path = file_path.resolve()
            if resolved_path in generated_files:
                continue

            try:
                contents = file_path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue

            if MARKER in contents or POST_TAGS_MARKER_START in contents:
                file_path.unlink()

        for directory_path in sorted((path for path in directory.rglob("*") if path.is_dir()), reverse=True):
            if any(directory_path.iterdir()):
                continue
            directory_path.rmdir()

    update_myst_toc(posts_by_tag, all_posts)
    update_blog_page(all_posts)
    print(
        f"Generated {len(generated_files)} tag page(s) in {BLOG_TAGS_DIR} and updated {MYST_YML_PATH.name} and {BLOG_MD_PATH.name}."
    )


if __name__ == "__main__":
    main()