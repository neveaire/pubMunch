# per-publisher configuration for pubCrawl.py
from os.path import *
import logging, urllib2, urlparse, urllib, re
import pubConf, pubGeneric, maxCommon, html, maxCommon

# crawler delay config, values in seconds
# these overwrite the default set with the command line switch to pubCrawl
# special case is highwire, handled in the code:
# (all EST): mo-fri: 9-5pm: 120 sec, mo-fri 5pm-9am: 10 sec, sat-sun: 5 sec (no joke) 
crawlDelays = {
    "www.nature.com"              : 10,
    "onlinelibrary.wiley.com" : 1,
    "dx.doi.org"              : 1,
    "ucelinks.cdlib.org"      : 20,
    "eutils.ncbi.nlm.nih.gov"      : 3,
    "sciencedirect.com"      : 15
}

def parseHighwire():
    """ create two dicts 
    printIssn -> url to pmidlookup-cgi of highwire 
    and 
    publisherName -> top-level hostnames
    >>> temps, domains = parseHighwire()
    >>> temps['0270-6474']
    u'http://www.jneurosci.org/cgi/pmidlookup?view=long&pmid=%(pmid)s'
    >>> domains["Society for Neuroscience"]
    set([u'jneurosci'])
    """
    # highwire's publisher names are not resolved ("SAGE", "SAGE Pub", etc)
    # so: first get dict printIssn -> resolved publisherName from publishers.tab
    pubFname = join(pubConf.publisherDir, "publishers.tab")
    pIssnToPub = {}
    for row in maxCommon.iterTsvRows(pubFname):
        if not row.pubName.startswith("HIGHWIRE"):
            continue
        for issn in row.journalIssns.split("|"):
            issn = issn.rstrip(" ")
            pIssnToPub[issn] = row.pubName.replace("HIGHWIRE ","").strip()

    # go over highwire table and make dict pubName -> issn -> templates
    # and dict pubName -> domains
    fname = join(pubConf.journalListDir, "highwire.tab")
    templates = {}
    domains = {}
    for row in maxCommon.iterTsvRows(fname, encoding="latin1"):
        if row.eIssn.strip()=="Unknown":
            continue
        pubName = pIssnToPub[row.pIssn.strip()].strip()
        templates.setdefault(pubName, {})
        templates[row.pIssn.strip()] = row.urls.strip()+"/cgi/pmidlookup?view=long&pmid=%(pmid)s" 

        host = urlparse.urlparse(row.urls).hostname
        domain = ".".join(host.split('.')[-2:]).strip()
        domains.setdefault(pubName, set()).add(domain)

    return templates, domains
     
def highwireConfigs():
    " return dict publisher name -> config for all highwire publishers "
    logging.info("Creating config for Highwire publishers")
    res = {}
    issnTemplates, pubDomains = parseHighwire()

    for pubName, domains in pubDomains.iteritems():
        templates = {}
        for issn, templUrl in issnTemplates.iteritems():
            for domain in domains:
                if domain in templUrl:
                    templates[issn]=templUrl
                    break
                    
        res[pubName] = {
            "hostnames" : domains,
            "landingUrl_templates" : templates,
            "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
            "doiUrl_replace" : {"$" : ".long"},
            "landingUrl_isFulltextKeyword" : ".long",
            "landingPage_ignoreMetaTag" : True,
            "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
            "landingPage_suppFileList_urlREs" : [".*/content.*suppl/DC[0-9]"],
            "suppListPage_suppFile_urlREs" : [".*/content.*suppl/.*"],
        }
    return res

highwireCfg = highwireConfigs()

# crawl configuration: for each website, define how to crawl the pages
confDict = {
    "oup" :
        highwireCfg["Oxford University Press"],

    "elsevier" :
    # at UCSC we don't use this, we get elsevier data via consyn.elsevier.dom
    # this is mostly for off-site use or for the odd project that doesn't
    # want to pull from consyn
    # caveats:  
    # * we cannot download text html (no function to add np=y to landing url)
    # * we don't know if we actually have access to an article 
    # * no supplemental files 
    {
        "hostnames" : ["www.sciencedirect.com"],
        #only pdfs "landingUrl_replaceREs" : {"$" : "?np=y"}, # switch sd to screen reader mode
        "landingPage_stopPhrases": ["make a payment", "purchase this article", \
            "This is a one-page preview only"],
        "landingPage_mainLinkTextREs" : ["PDF  +\([0-9]+ K\)"],
    },

    "npg" :
    # http://www.nature.com/nature/journal/v463/n7279/suppinfo/nature08696.html
    # http://www.nature.com/pr/journal/v42/n4/abs/pr19972520a.html - has no pdf
    # 
    {
        "hostnames" : ["www.nature.com"],
        "landingPage_stopPhrases": ["make a payment", "purchase this article"],
        "landingPage_acceptNoPdf": True,
        "landingUrl_isFulltextKeyword" : "full",
        "landingUrl_fulltextUrl_replace" : {"full" : "pdf", "html" : "pdf", "abs" : "pdf"},
        "landingPage_mainLinkTextREs" : ["Download PDF"],
        "landingUrl_suppListUrl_replace" : {"full" : "suppinfo", "abs" : "suppinfo"},
        "landingPage_suppListTextREs" : ["Supplementary information index", "[Ss]upplementary [iI]nfo", "[sS]upplementary [iI]nformation"],
        "suppListPage_suppFileTextREs" : ["[Ss]upplementary [dD]ata.*", "[Ss]upplementary [iI]nformation.*", "Supplementary [tT]able.*", "Supplementary [fF]ile.*", "Supplementary [Ff]ig.*", "Supplementary [lL]eg.*", "Download PDF file.*", "Supplementary [tT]ext.*", "Supplementary [mM]ethods.*", "Supplementary [mM]aterials.*", "Review Process File"]
    # Review process file for EMBO, see http://www.nature.com/emboj/journal/v30/n13/suppinfo/emboj2011171as1.html
    },

    # with suppl
    # PMID 22017543
    # http://online.liebertpub.com/doi/full/10.1089/nat.2011.0311
    # with html
    # PMID 22145933
    # http://online.liebertpub.com/doi/abs/10.1089/aid.2011.0232
    # no html
    # PMID 7632460
    # http://online.liebertpub.com/doi/abs/10.1089/aid.1995.11.443
    "mal" :
    {
        "hostnames" : ["online.liebertpub.com"],
        "landingUrl_templates" : {"anyIssn" : "http://online.liebertpub.com/doi/full/%(doi)s"},
        "landingUrl_isFulltextKeyword" : "/full/",
        "landingUrl_fulltextUrl_replace" : {"/abs/" : "/full/" },
        "landingPage_mainLinkTextREs" : ["Full Text PDF.*"],
        "landingPage_suppListTextREs" : ["Supplementary materials.*"]
    },

    # https://www.jstage.jst.go.jp/article/circj/75/4/75_CJ-10-0798/_article
    # suppl file download does NOT work: strange javascript links
    "jstage" :
    {
        "hostnames" : ["www.jstage.jst.go.jp"],
        "landingUrl_fulltextUrl_replace" : {"_article" : "_pdf" },
        "landingPage_mainLinkTextREs" : ["Full Text PDF.*"],
        "landingPage_suppListTextREs" : ["Supplementary materials.*"]
    },
    # rupress tests:
    # PMID 12515824 - with integrated suppl files into main PDF
    # PMID 15824131 - with separate suppl files
    # PMID 8636223  - landing page is full (via Pubmed), abstract via DOI
    # cannot do suppl zip files like this one http://jcb.rupress.org/content/169/1/35/suppl/DC1
    # 
    "rupress" :
    {
        "hostnames" : ["rupress.org", "jcb.org"],
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignorePageWords" : ["From The Jcb"],
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf"},
        "suppListPage_addSuppFileTypes" : ["html", "htm"], # pubConf does not include htm/html
        "landingPage_mainLinkTextREs" : ["Full Text (PDF)"],
        #"landingPage_suppListTextREs" : ["Supplemental [Mm]aterial [Iindex]", "Supplemental [Mm]aterial"],
        "landingUrl_suppListUrl_replace" : {".long" : "/suppl/DC1", ".abstract" : "/suppl/DC1"},
        "suppListPage_suppFileTextREs" : ["[Ss]upplementary [dD]ata.*", "[Ss]upplementary [iI]nformation.*", "Supplementary [tT]able.*", "Supplementary [fF]ile.*", "Supplementary [Ff]ig.*", "[ ]+Figure S[0-9]+.*", "Supplementary [lL]eg.*", "Download PDF file.*", "Supplementary [tT]ext.*", "Supplementary [mM]aterials and [mM]ethods.*", "Supplementary [mM]aterial \(.*"],
        "ignoreSuppFileLinkWords" : ["Video"],
        "ignoreSuppFileContentText" : ["Reprint (PDF) Version"],
        "suppListPage_suppFile_urlREs" : [".*/content/suppl/.*"]
    },
    # http://jb.asm.org/content/194/16/4161.abstract = PMID 22636775
    "asm" :
    {
        "hostnames" : ["asm.org"],
        "landingUrl_isFulltextKeyword" : ".long",
        "doiUrl_replace" : {"$" : ".long"},
        "landingPage_ignoreMetaTag" : True,
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # if found on landing page Url, wait for 15 minutes and retry
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        #"landingUrl_fulltextUrl_replace" : {"long" : "full.pdf?with-ds=yes", "abstract" : "full.pdf?with-ds=yes" },
        #"landingUrl_suppListUrl_replace" : {".long" : "/suppl/DCSupplemental", ".abstract" : "/suppl/DCSupplemental"},
        "landingPage_suppFileList_urlREs" : [".*suppl/DCSupplemental"],
        "suppListPage_suppFile_urlREs" : [".*/content/suppl/.*"],
    },
    # 
    # 21159627 http://cancerres.aacrjournals.org/content/70/24/10024.abstract has suppl file
    "aacr" :
    {
        "hostnames" : ["aacrjournals.org"],
        "landingUrl_templates" : {"0008-5472" : "http://cancerres.aacrjournals.org/content/%(vol)s/%(issue)s/%(firstPage)s.long"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content[0-9/]*suppl/DC1"],
        "suppListPage_suppFile_urlREs" : [".*/content[0-9/]*suppl/.*"],
        "landingPage_stopPhrases" : ["Purchase Short-Term Access"]
    },
    # 1995 PMID 7816814 
    # 2012 PMID 22847410 has one supplement, has suppl integrated in paper
    "cshlp" :
    {
        "hostnames" : ["cshlp.org"],
        "landingUrl_templates" : {"1355-8382" : "http://rnajournal.cshlp.org/content/%(vol)s/%(issue)s/%(firstPage)s.full"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content[0-9/]*suppl/DC1"],
        "suppListPage_suppFile_urlREs" : [".*/content[0-9/]*suppl/.*"],
        "landingPage_stopPhrases" : ["Purchase Short-Term Access"]
    },
    "pnas" :
    {
        "hostnames" : ["pnas.org"],
        "landingUrl_templates" : {"0027-8424" : "http://pnas.org/cgi/pmidlookup?view=long&pmid=%(pmid)s"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*suppl/DCSupplemental"],
        "suppListPage_suppFile_urlREs" : [".*/content/suppl/.*"],
    },
    "aspet" :
    {
        "hostnames" : ["aspetjournals.org"],
        "landingUrl_templates" : {"0022-3565" : "http://jpet.aspetjournals.org/cgi/pmidlookup?view=long&pmid=%(pmid)s"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content[0-9/]*suppl/DC1"],
        "suppListPage_suppFile_urlREs" : [".*/content[0-9/]*suppl/.*"],
    },
    "faseb" :
    {
        "hostnames" : ["fasebj.org"],
        "landingUrl_templates" : {"0892-6638" : "http://www.fasebj.org/cgi/pmidlookup?view=long&pmid=%(pmid)s"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content[0-9/]*suppl/DC1"],
        "suppListPage_suppFile_urlREs" : [".*/content[0-9/]*suppl/.*"],
    },
    # society of leukocyte biology
    # PMID 20971921
    "slb" :
    {
        "hostnames" : ["jleukbio.org"],
        "landingUrl_templates" : {"0741-5400" : "http://www.jleukbio.org/cgi/pmidlookup?view=long&pmid=%(pmid)s"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content[0-9/]*suppl/DC1"],
        "suppListPage_suppFile_urlREs" : [".*/content[0-9/]*suppl/.*"],
    },
    # Company of Biologists
    "cob" :
    {
        "hostnames" : ["biologists.org"],
        "landingUrl_templates" : {"0950-1991" : "http://dev.biologists.org/cgi/pmidlookup?view=long&pmid=%(pmid)s", "0022-0949" : "http://jcs.biologists.org/cgi/pmidlookup?view=long&pmid=%(pmid)s"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content[0-9/]*suppl/DC1"],
        "suppListPage_suppFile_urlREs" : [".*/content[0-9/]*suppl/.*"],
    },
    # Genetics Society of America
    # PMID 22714407
    "genetics" :
    {
        "hostnames" : ["genetics.org"],
        "landingUrl_templates" : {"0016-6731" : "http://genetics.org/cgi/pmidlookup?view=long&pmid=%(pmid)s"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content[0-9/]*suppl/DC1"],
        "suppListPage_suppFile_urlREs" : [".*/content[0-9/]*suppl/.*"],
    },
    # Society of General Microbiology
    # PMID 22956734
    # THEY USE DC1 AND DC2 !!! Currently we're missing the DC1 or DC2 files... :-(
    # todo: invert linkdict to link -> text and not text -> link
    # otherwise we miss one link if we see twice "supplemental table" (see example)
    "sgm" :
    {
        "hostnames" : ["sgmjournals.org"],
        "landingUrl_templates" : {\
            "1466-5026" : "http://ijs.sgmjournals.org/cgi/pmidlookup?view=long&pmid=%(pmid)s", \
            "1350-0872" : "http://mic.sgmjournals.org/cgi/pmidlookup?view=long&pmid=%(pmid)s", \
            "0022-2615" : "http://jmm.sgmjournals.org/cgi/pmidlookup?view=long&pmid=%(pmid)s", \
            "0022-1317" : "http://vir.sgmjournals.org/cgi/pmidlookup?view=long&pmid=%(pmid)s"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content.*suppl/DC[0-9]"],
        "suppListPage_suppFile_urlREs" : [".*/content.*suppl/.*"],
    },
    # SMBE - Soc of Mol Biol and Evol
    # part of OUP - careful, duplicates!
    # PMID 22956734
    "smbe" :
    {
        "hostnames" : ["mbe.oxfordjournals.org"],
        "landingUrl_templates" : \
            {"0737-4038" : "http://mbe.oxfordjournals.org/cgi/pmidlookup?view=long&pmid=%(pmid)s"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content.*suppl/DC[0-9]"],
        "suppListPage_suppFile_urlREs" : [".*/content.*suppl/.*"],
    },
    # http://www.jimmunol.org/content/189/11/5129/suppl/DC1
    # http://www.jimmunol.org/content/suppl/2012/10/25/jimmunol.1201570.DC1/12-01570_S1-4_ed10-24.pdf
    "aai" :
    {
        "hostnames" : ["jimmunol.org"],
        "landingUrl_templates" : {"0022-1767" : "http://www.jimmunol.org/cgi/pmidlookup?view=long&pmid=%(pmid)s"},
        "landingPage_errorKeywords" : "We are currently doing routine maintenance", # wait for 15 minutes and retry
        "doiUrl_replace" : {"$" : ".long"},
        "landingUrl_isFulltextKeyword" : ".long",
        "landingPage_ignoreMetaTag" : True,
        "landingUrl_fulltextUrl_replace" : {"long" : "full.pdf", "abstract" : "full.pdf" },
        "landingPage_suppFileList_urlREs" : [".*/content[0-9/]*suppl/DC1"],
        "suppListPage_suppFile_urlREs" : [".*/content/suppl/.*"],
    },
    # example suppinfo links 20967753 (major type of suppl, some also have "legacy" suppinfo
    # example spurious suppinfo link 8536951
    # 
    "wiley" :
    {
        "hostnames" : ["onlinelibrary.wiley.com"],
        #"landingUrl_templates" : {None: "http://onlinelibrary.wiley.com/doi/%(doi)s/full"},
        "doiUrl_replace" : {"abstract" : "full"},
        "landingUrl_isFulltextKeyword" : "full",
        "landingUrl_fulltextUrl_replace" : {"full" : "pdf", "abstract" : "pdf"},
        "landingPage_suppListTextREs" : ["Supporting Information"],
        "suppListPage_suppFile_urlREs" : [".*/asset/supinfo/.*", ".*_s.pdf"],
        "suppFilesAreOffsite" : True,
        "landingPage_ignoreUrlREs"  : ["http://onlinelibrary.wiley.com/resolve/openurl.genre=journal&issn=[0-9-X]+/suppmat/"],
        "landingPage_stopPhrases" : ["You can purchase online access", "Registered Users please login"]
    },
    # http://www.futuremedicine.com/doi/abs/10.2217/epi.12.21
    "futureScience" :
    {
        "hostnames" : ["futuremedicine.com", "future-science.com", "expert-reviews.com", "future-drugs.com"],
        "landingUrl_fulltextUrl_replace" : {"abs" : "pdfplus"},
        "landingUrl_suppListUrl_replace" : {"abs" : "suppl"},
        "suppListPage_suppFile_urlREs" : [".*suppl_file.*"],
        "landingPage_stopPhrases" : ["single article purchase is required", "The page you have requested is unfortunately unavailable"]
    },

}

def compileRegexes():
    " compile regexes in confDict "
    ret = {}
    for pubId, crawlConfig in confDict.iteritems():
        ret[pubId] = {}
        for key, values in crawlConfig.iteritems():
            if key.endswith("REs"):
                newValues = []
                for regex in values:
                    newValues.append(re.compile(regex))
            else:
                newValues = values
            ret[pubId][key] = newValues
    return ret


def prepConfigIndexByHost():
    """ compile regexes in config and return dict publisherId -> config and hostname -> config 
    these make it possible to get the config either by hostname (for general mode)
    or by publisher (for per-publisher mode)
    """
    compCfg = compileRegexes()
    byHost = {}
    for pubId, crawlConfig in compCfg.iteritems():
        for host in crawlConfig["hostnames"]:
            byHost[host] = crawlConfig
    return compCfg, byHost
