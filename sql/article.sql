#Publications tracks article meta data
CREATE TABLE article (
    articleId bigint not null,	# internal article ID, created during download
    extId varchar(255) not null,	# publisher internal ID e.g. PMCxxxx or doi or PMIDxxxx, or PPI
    source varchar(255),	# the origin of the article, something like elsevier, pmc, pubmed or crawler
    publisher varchar(255),     # code of publisher, something like elsevier, aai, pmc or pnas
    origFile varchar(1000),     # original file from which this was imported, e.g. zipfile or tarfile
    journal varchar(1000),	# journal or book title
    printIssn varchar(255),	# ISSN of the print edition of the article
    eIssn varchar(255),	 # optional: ISSN of the electronic edition of the journal/book 
    journalUniqueId varchar(255),	 # only medline: nlm unique journal ID
    year varchar(255),	 # first year of publication (electronic or print or advanced access)
    articleType varchar(255), # research-article, review or other
    articleSection varchar(255),  # the section of the book/journal, e.g. "methods", "chapter 5" or "Comments"
    authors varchar(3000) default null,	# author list for this article
    authorEmails varchar(3000) default null,	# author list for this article
    authorAffiliations varchar(3000) default null,	# affiliations of article authors
    keywords varchar(3000) default null,	# keywords, e.g. MESH terms for Pubmed
    title varchar(2000) default null,	# article title
    abstract varchar(32000) not null,	# article abstract
    vol varchar(255),      # volume
    issue varchar(255),    # issue
    page varchar(255),     # first page of article, can be ix, x, or S4
    pmid varchar(255),            # PubmedID if available
    pmcId varchar(255),           # Pubmed Central ID
    doi varchar(255),             # DOI, without leading doi:
    fulltextUrl varchar(255),     # URL to fulltext of article
    time  varchar(255),    # date of download
    PRIMARY KEY(articleId),
    KEY pmcId(pmcId),
    KEY pmid(pmid),
    KEY doi(doi)
)
DEFAULT CHARACTER SET 'utf8'
;
