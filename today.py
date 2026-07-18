"""
Updates dark_mode.svg / light_mode.svg with live GitHub stats.
Architecture inspired by Andrew6rant/Andrew6rant.

Env vars:
  ACCESS_TOKEN  GitHub PAT (repo + read:user)
  USER_NAME     GitHub username        (default: Nikhil210206)
  BIRTHDAY      YYYY-MM-DD for uptime  (default: 2006-02-21)
"""

import datetime
import os
from xml.dom import minidom

import requests
from dateutil import relativedelta

API = "https://api.github.com/graphql"
USER = os.environ.get("USER_NAME", "Nikhil210206")
HEADERS = {"Authorization": f"bearer {os.environ['ACCESS_TOKEN']}"}
fmt = "{:,}".format


def gql(query, variables=None):
    r = requests.post(API, json={"query": query, "variables": variables or {}},
                      headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "errors" in data:
        raise RuntimeError(data["errors"])
    return data["data"]


def user_id_and_followers():
    q = """
    query($login: String!) {
      user(login: $login) { id followers { totalCount } }
    }"""
    d = gql(q, {"login": USER})["user"]
    return d["id"], d["followers"]["totalCount"]


def repo_stats():
    """Owned, non-fork repos: count, total stars, and names."""
    q = """
    query($login: String!, $cursor: String) {
      user(login: $login) {
        repositories(first: 100, after: $cursor,
                     ownerAffiliations: OWNER, isFork: false) {
          totalCount
          pageInfo { hasNextPage endCursor }
          nodes { nameWithOwner stargazerCount }
        }
      }
    }"""
    repos, stars, names, cursor = 0, 0, [], None
    while True:
        d = gql(q, {"login": USER, "cursor": cursor})["user"]["repositories"]
        repos = d["totalCount"]
        for n in d["nodes"]:
            stars += n["stargazerCount"]
            names.append(n["nameWithOwner"])
        if not d["pageInfo"]["hasNextPage"]:
            return repos, stars, names
        cursor = d["pageInfo"]["endCursor"]


def commits_and_loc(user_id, repo_names):
    """Walk default-branch history authored by me in every owned repo."""
    q = """
    query($owner: String!, $name: String!, $id: ID!, $cursor: String) {
      repository(owner: $owner, name: $name) {
        defaultBranchRef {
          target { ... on Commit {
            history(first: 100, after: $cursor, author: {id: $id}) {
              totalCount
              pageInfo { hasNextPage endCursor }
              nodes { additions deletions }
            }
          } }
        }
      }
    }"""
    commits = added = deleted = 0
    for full in repo_names:
        owner, name = full.split("/")
        cursor, counted = None, False
        while True:
            ref = gql(q, {"owner": owner, "name": name,
                          "id": user_id, "cursor": cursor})["repository"]["defaultBranchRef"]
            if ref is None:  # empty repo
                break
            h = ref["target"]["history"]
            if not counted:
                commits += h["totalCount"]
                counted = True
            for c in h["nodes"]:
                added += c["additions"]
                deleted += c["deletions"]
            if not h["pageInfo"]["hasNextPage"]:
                break
            cursor = h["pageInfo"]["endCursor"]
    return commits, added, deleted


def age_string(birthday):
    diff = relativedelta.relativedelta(datetime.datetime.today(), birthday)
    def p(n, w):
        return f"{n} {w}{'s' if n != 1 else ''}"
    return f"{p(diff.years, 'year')}, {p(diff.months, 'month')}, {p(diff.days, 'day')}"


def update_svg(path, values):
    doc = minidom.parse(path)
    for el in doc.getElementsByTagName("tspan"):
        if el.getAttribute("id") in values:
            el.firstChild.data = values[el.getAttribute("id")]
    with open(path, "w", encoding="utf-8") as f:
        f.write(doc.toxml())


def main():
    birthday = datetime.datetime.strptime(
        os.environ.get("BIRTHDAY", "2006-02-21"), "%Y-%m-%d")
    uid, followers = user_id_and_followers()
    repos, stars, names = repo_stats()
    commits, added, deleted = commits_and_loc(uid, names)
    values = {
        "age_data": age_string(birthday),
        "repo_data": fmt(repos),
        "star_data": fmt(stars),
        "follower_data": fmt(followers),
        "commit_data": fmt(commits),
        "loc_data": fmt(added - deleted),
        "loc_add": fmt(added) + "++",
        "loc_del": fmt(deleted) + "--",
    }
    for svg in ("dark_mode.svg", "light_mode.svg"):
        update_svg(svg, values)
    print("Updated:", values)


if __name__ == "__main__":
    main()
