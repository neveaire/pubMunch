import logging, os, sys, tempfile, csv, collections, types, codecs, gzip, os.path, re, glob
from types import *

def errAbort(text):
    raise Exception(text)
    
def mustExistDir(path, makeDir=False):
    if not os.path.isdir(path):
        if makeDir:
            logging.info("Creating directory %s" % path)
            os.makedirs(path)
        else:
            logging.error("Directory %s does not exist" % path)
            raise Exception()

def mustExist(path):
    if not (os.path.isdir(path) or os.path.isfile(path)):
        logging.error("%s is not a directory or file" % path)
        sys.exit(1)

def mustNotExist(path):
    if (os.path.isdir(path) or os.path.isfile(path)):
        logging.error("%s already exists" % path)
        sys.exit(1)

def mustNotBeEmptyDir(path):
    mustExist(path)
    fileList = os.listdir(path)
    if len(fileList)==0:
        logging.error("dir %s does not contain any files" % path)
        sys.exit(1)

def mustBeEmptyDir(path, makeDir=False):
    " exit if path does not exist or it not empty. do an mkdir if makeDir==True "
    if type(path)==types.ListType:
        for i in path:
            mustBeEmptyDir(i, makeDir=makeDir)
    else:
        if not os.path.isdir(path):
            if not makeDir:
                raise Exception("Directory %s does not exist" % path)
            else:
                logging.info("Creating directory %s" % path)
                os.makedirs(path)
        else:
            if len(os.listdir(path))!=0:
                raise Exception("Directory %s is not empty" % path)

def makeTempFile(tmpDir=None, prefix="tmp", ext=""):
    """ return a REAL temporary file object
    the user is responsible for deleting it!
    """
    fd, filename = tempfile.mkstemp(suffix=ext, dir=tmpDir, prefix=prefix)
    fileObject = os.fdopen(fd, "wb")
    return fileObject, filename

def joinMkdir(*args):
    """ join paths like os.path.join, do an mkdir, ignore all errors """
    path = os.path.join(*args)
    if not os.path.isdir(path):
        logging.debug("Creating dir %s" % path)
        os.makedirs(path)
    return path

def iterCsvRows(path, headers=None):
    " iterate over rows of csv file, uses the csv.reader, see below for homemade version "
    Rec = None
    for row in csv.reader(open(path, "rb")):
        if headers == None:
            headers = row
            headers = [re.sub("[^a-zA-Z]","_", h) for h in headers]
            Rec = collections.namedtuple("iterCsvRow", headers)
            continue
        fields = Rec(*row)
        yield fields

def iterTsvDir(inDir, ext=".tab.gz", headers=None, format=None, fieldTypes=None, \
            noHeaderCount=None, encoding="utf8", fieldSep="\t"):
    " run iterTsvRows on all .tab or .tab.gz files in inDir "
    inMask = os.path.join(inDir, "*"+ext)
    inFnames = glob.glob(inMask)
    logging.debug("Found files %s" % inFnames)
    pm = ProgressMeter(len(inFnames))
    if len(inFnames)==0:
        raise Exception("No file matches %s" % inMask)

    for inFname in inFnames:
        for row in iterTsvRows(inFname, headers, format, fieldTypes, noHeaderCount, encoding, fieldSep):
            yield row
        pm.taskCompleted()

def iterTsvRows(inFile, headers=None, format=None, noHeaderCount=None, fieldTypes=None, encoding="utf8", fieldSep="\t"):
    """ 
        parses tab-sep file with headers as field names 
        yields collection.namedtuples
        strips "#"-prefix from header line

        if file has no headers: 
        
        a) needs to be called with 
        noHeaderCount set to number of columns.
        headers will then be named col0, col1, col2, col3, etc...

        b) you can also set headers to a list of strings
        and supply header names in that way.
    
        c) set the "format" to one of: psl, this will also do type conversion

        fieldTypes can be a list of types.xxx objects that will be used for type
        conversion (e.g. types.IntType)
    """

    if noHeaderCount:
        numbers = range(0, noHeaderCount)
        headers = ["col" + str(x) for x in numbers]

    if format=="psl":
        headers =      ["score", "misMatches", "repMatches", "nCount", "qNumInsert", "qBaseInsert", "tNumInsert", "tBaseInsert", "strand",    "qName",    "qSize", "qStart", "qEnd", "tName",    "tSize", "tStart", "tEnd", "blockCount", "blockSizes", "qStarts", "tStarts"]
        fieldTypes =   [IntType, IntType,      IntType,      IntType,  IntType,      IntType,       IntType,       IntType,      StringType,  StringType, IntType, IntType,  IntType,StringType, IntType, IntType,  IntType,IntType ,     StringType,   StringType,StringType]

    if isinstance(inFile, str):
        if inFile.endswith(".gz"):
            zf = gzip.open(inFile, 'rb')
            reader = codecs.getreader(encoding)
            fh = reader(zf)
        else:
            fh = codecs.open(inFile, encoding=encoding)
    else:
        fh = inFile

    if headers==None:
        line1 = fh.readline()
        line1 = line1.strip("\n").strip("#")
        headers = line1.split(fieldSep)
        headers = [re.sub("[^a-zA-Z0-9_]","_", h) for h in headers]

    Record = collections.namedtuple('tsvRec', headers)
    for line in fh:
        fields = line.strip("\n").split(fieldSep)
        if fields[0]=='2003253450001':
            print repr(fields)
        #fields = [x.decode(encoding) for x in fields]
        if fieldTypes:
            fields = [f(x) for f, x in zip(fieldTypes, fields)]
        try:
            rec = Record(*fields)
        except Exception, msg:
            logging.error("Exception occured while parsing line, %s" % msg)
            logging.error("Filename %s" % fh.name)
            logging.error("Line was: %s" % line)
            logging.error("Does number of fields match headers?")
            logging.error("Headers are: %s" % headers)
            sys.exit(1)
        # convert fields to correct data type
        yield rec

def iterTsvGroups(fileObject, **kwargs):
    """ 
    iterate over a tab sep file, convert lines to namedtuples (records), group lines by some field.

    file needs to be sorted on this field!
    parameters:
        groupFieldNumber: the index (int) of the field to group on
        useChar: only use these chars of the groupField

    return:
        (groupId, list of namedtuples)
    """
    groupFieldNumber = kwargs.get("groupFieldNumber", 0)
    useChars = kwargs.get("useChars", None)
    if "groupFieldNumber" in kwargs:
        del kwargs["groupFieldNumber"]
    if useChars:
        del kwargs["useChars"]
    assert(groupFieldNumber!=None)

    lastId = None
    group = []
    for rec in iterTsvRows(fileObject, **kwargs):
        id = rec[groupFieldNumber]
        if useChars:
            id = id[:useChars]
        if lastId==None:
            lastId = id
        if lastId==id:
            group.append(rec)
        else:
            yield lastId, group
            group = [rec]
            lastId = id
    yield id, group
    
def runCommand(cmd, ignoreErrors=False, verbose=False):
    """ run command in shell, exit if not successful """
    msg = "Running shell command: %s" % cmd
    logging.debug(msg)
    if verbose:
        logging.info(msg)
    ret = os.system(cmd)
    if ret!=0:
        if ignoreErrors:
            logging.info("Could not run command %s" % cmd)
            logging.info("Error message ignored, program will continue")
        else:
            raise Exception("Could not run command (Exitcode %d): %s" % (ret, cmd))

def makedirs(path, quiet=False):
    try:
        os.makedirs(path)
    except:
        if not quiet:
            raise 

def appendTsvNamedtuple(filename, row):
    " append a namedtuple to a file. Write headers if file does not exist "
    if not os.path.isfile(filename):
       outFh = open(filename, "w") 
       headers = row._fields
       outFh.write("\t".join(headers)+"\n")
    else:
       outFh = open(filename, "a")
    outFh.write("\t".join(row)+"\n")

def appendTsvOrderedDict(filename, orderedDict):
    " append a namedtuple to a file. Write headers if file does not exist "
    headers = []
    values = []
    for key, val in orderedDict.iteritems():
        headers.append(key)
        values.append(val)

    if not os.path.isfile(filename):
       outFh = codecs.open(filename, "w", encoding="utf8") 
       outFh.write("\t".join(headers)+"\n")
    else:
       outFh = codecs.open(filename, "a", encoding="utf8") 
    outFh.write(u"\t".join(values)+"\n")

class ProgressMeter:
    """ prints a message "x% done" every stepCount calls
    """
    def __init__(self, taskCount, stepCount=20, quiet=False):
        self.taskCount=taskCount
        self.stepCount=stepCount
        self.tasksPerMsg = taskCount/stepCount
        self.i=0
        self.quiet = quiet
        #print "".join(9*["."])

    def taskCompleted(self):
        if self.quiet:
            return
        logging.debug("task completed called, i=%d, tasksPerMsg=%d" % (self.i, self.tasksPerMsg))
        if self.tasksPerMsg!=0 and self.i % self.tasksPerMsg == 0:
            donePercent = (self.i*100) / self.taskCount
            #print "".join(5*[chr(8)]),
            print ("%.2d%% " % donePercent),
            sys.stdout.flush()
        self.i+=1
        if self.i==self.taskCount:
            print ""

def test():
    pm = ProgressMeter(2000)
    for i in range(0,2000):
        pm.taskCompleted()

def parseConfig(f):
    " parse a name=value file from file-like object f and return as dict"
    if isinstance(f, str):
        logging.debug("parsing config file %s" % f)
        f = open(os.path.expanduser(f))
    result = {}
    for line in f:
        if line.startswith("#"):
            continue
        line = line.strip()
        if "=" in line:
            key, val = line.split("=")
            result[key]=val
    return result

if __name__=="__main__":
    test()