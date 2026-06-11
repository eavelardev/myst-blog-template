# MyST Blog Template

This tool creates tags sections from posts.

## Test the tool

Create a MyST project or use an existing one.

```
myst init --project --site
```

Add posts to `blog/posts` using this format

```
---
title: First post
date: 2022-05-11
authors:
  - name: Eduardo Avelar
    email: eavelardev@gmail.com
    github: eavelardev
thumbnail: /site_logo.png
tags:
  - AWS
---

Content of my first post
```

Add the respective `.png` image to the project, in this case is `site_logo.png`

`blog/blog.md` will be created if doesn't exists

Add `myst` and `generate_blog.py` tools to the project

Execute `./myst build` or `./myst start`

If `./myst` can't be executed:
```
chmod +x ./myst
```

Feel free to contribute to this template