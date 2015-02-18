#!/usr/bin/env python

import chdb

import wikitools
import mwparserfromhell

import sys
import urlparse

WIKIPEDIA_BASE_URL = 'https://en.wikipedia.org'
WIKIPEDIA_WIKI_URL = WIKIPEDIA_BASE_URL + '/wiki/'
WIKIPEDIA_API_URL = WIKIPEDIA_BASE_URL + '/w/api.php'

MARKER = '7b94863f3091b449e6ab04d44cb372a0' # unlikely to be in any article
CITATION_NEEDED_HTML = '<span class="citation-needed">[citation needed]</span>'

# Monkey-patch mwparserfromhell so it strips some templates and tags the way
# we want.
def template_strip(self, normalize, collapse):
    if self.name == 'convert':
        return ' '.join(map(unicode, self.params[:2]))
mwparserfromhell.nodes.Template.__strip__ = template_strip

def tag_strip(self, normalize, collapse):
    if self.tag == 'ref':
        return None
    return self._original_strip(normalize, collapse)
mwparserfromhell.nodes.Tag._original_strip = mwparserfromhell.nodes.Tag.__strip__
mwparserfromhell.nodes.Tag.__strip__ = tag_strip

def is_citation_needed(t):
    return t.name.matches('Citation needed') or t.name.matches('cn')

def reload_snippets(db):
    cursor = db.cursor()
    wikipedia = wikitools.wiki.Wiki(WIKIPEDIA_API_URL)
    category = wikitools.Category(wikipedia, 'All_articles_with_unsourced_statements')
    for page in category.getAllMembersGen():
        wikitext = page.getWikiText()

        # FIXME we should only add each paragraph once
        for paragraph in wikitext.splitlines():
            wikicode = mwparserfromhell.parse(paragraph)

            for t in wikicode.filter_templates():
                if is_citation_needed(t):
                    stripped_len = len(wikicode.strip_code())
                    if stripped_len > 420 or stripped_len < 140:
                        # TL;DR or too short
                        continue

                    # add the marker so we know where the Citation-needed template
                    # was, and remove all markup (including the template)
                    wikicode.insert_before(t, MARKER)
                    snippet = wikicode.strip_code()
                    snippet = snippet.replace(MARKER, CITATION_NEEDED_HTML)

                    url = WIKIPEDIA_WIKI_URL + urlparse.unquote(page.urltitle)
                    url = unicode(url, 'utf-8')

                    row = (snippet, url, page.title)
                    assert all(type(x) == unicode for x in row)
                    try:
                        cursor.execute('''
                            INSERT INTO cn VALUES (?, ?, ?) ''', row)
                        db.commit()
                    except:
                        print >>sys.stderr, 'failed to insert %s in the db' % repr(row)

if __name__ == '__main__':
    db = chdb.init_db()
    reload_snippets(db)
    db.close()