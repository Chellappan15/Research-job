"""Canned external responses used by the ingestion tests (no network access)."""

RSS = b"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:media="http://search.yahoo.com/mrss/">
<channel>
  <title>AI Weekly</title>
  <item>
    <title>New &lt;b&gt;open&lt;/b&gt; model released</title>
    <link>https://news.example.com/posts/open-model/?utm_source=rss&amp;id=7</link>
    <guid>post-1</guid>
    <description><![CDATA[<p>A <em>new</em> open-weights model.</p>]]></description>
    <pubDate>Wed, 11 Nov 2026 09:30:00 GMT</pubDate>
    <media:thumbnail url="https://news.example.com/img/1.jpg"/>
  </item>
  <item>
    <title>No date, no guid</title>
    <link>http://WWW.News.Example.com/posts/no-date#comments</link>
  </item>
  <item>
    <link>https://news.example.com/posts/untitled</link>
    <guid>post-3</guid>
    <description>Entry without a title</description>
  </item>
  <item>
    <title>Entry without a link is skipped</title>
    <guid>post-4</guid>
  </item>
  <item>
    <title>Duplicate of post 1 via tracking URL</title>
    <link>https://news.example.com/posts/open-model?id=7&amp;utm_campaign=x</link>
    <guid>post-1-dup</guid>
  </item>
  <item>
    <title>Unsafe link scheme</title>
    <link>javascript:alert(1)</link>
    <guid>post-6</guid>
  </item>
</channel>
</rss>
"""

ATOM_GITHUB = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Release notes from transformers</title>
  <entry>
    <id>tag:github.com,2008:Repository/1/v5.0.0</id>
    <updated>2026-11-10T12:00:00Z</updated>
    <link rel="alternate" type="text/html" href="https://github.com/acme/transformers/releases/tag/v5.0.0"/>
    <title>v5.0.0</title>
    <content type="html">&lt;p&gt;Major release&lt;/p&gt;</content>
  </entry>
</feed>
"""

YOUTUBE = b"""<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns:yt="http://www.youtube.com/xml/schemas/2015"
      xmlns:media="http://search.yahoo.com/mrss/" xmlns="http://www.w3.org/2005/Atom">
  <title>AI Explained</title>
  <entry>
    <id>yt:video:abcDEF12345</id>
    <yt:videoId>abcDEF12345</yt:videoId>
    <yt:channelId>UCaaaaaaaaaaaaaaaaaaaaaa</yt:channelId>
    <title>Transformers in 10 minutes</title>
    <link rel="alternate" href="https://www.youtube.com/watch?v=abcDEF12345"/>
    <published>2026-11-12T15:00:00+00:00</published>
    <media:group>
      <media:title>Transformers in 10 minutes</media:title>
      <media:thumbnail url="https://i1.ytimg.com/vi/abcDEF12345/hqdefault.jpg"
                       width="480" height="360"/>
      <media:description>Attention, explained.</media:description>
    </media:group>
  </entry>
  <entry>
    <id>yt:video:zzzZZZ99999</id>
    <yt:videoId>zzzZZZ99999</yt:videoId>
    <title>Second video</title>
    <published>2026-11-11T15:00:00+00:00</published>
  </entry>
  <entry>
    <id>broken</id>
    <title>No video id</title>
  </entry>
</feed>
"""

NOT_A_FEED = b"\x00\x01 definitely not xml <<<"
