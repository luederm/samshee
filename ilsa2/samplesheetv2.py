from ilsa2.sectionedsheet import SectionedSheet, settings_to_string, data_to_string
from jsonschema import validate
import re
from collections import OrderedDict
import types
#
# a schema that validates a sectioned sheet to be a samplesheet
# we will put this elsewhere, but for now this is the place:
# this follows
# https://support-docs.illumina.com/IN/NextSeq10002000/Content/SHARE/SampleSheetv2/SampleSheetValidation_fNS_m2000_m1000.htm
# (which is not a proper spec, but reasonably close to it and this is my interpretation)
illuminasamplesheetv2schema = {
    "type": "object",
    "required": ["Header", "Reads", "Sequencing_Settings"],
    "properties": {
        "Header": {
            "type": "object",
            "required": ["FileFormatVersion"],
            "properties": {
                "FileFormatVersion": {
                    "type": "integer",
                    "const": 2
                },
                "RunName": {
                    "type": "string",
                    "pattern": "^[a-zA-Z0-9_\-\.]*$",
                    "description": "Unique run name of your preference. The RunName can contain alphanumeric characters, underscores, dashes, and periods. If the RunName contains spaces or special characters, analysis fails."
                },
                "RunDescription": {
                    "type": "string",
                    "description": "Description of the run"
                },
                "Instrument Type": {
                    "type": "string",
                    "description": "The instrument name",
                    "example": ["NextSeq 1000", "NextSeq 2000"]
                },
                "InstrumentPlatform": {
                    "type": "string",
                    "description": "The instrument platform name",
                    "example": ["NextSeq 1000", "NextSeq 2000"]
                }
            }
        },
        "Reads": {
            "type": "object",
            "required": ["Read1Cycles"],
            "properties": {
                "Read1Cycles": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Number of cycles in the first read. Ideally, this value should be 26 or greater. However, you can proceed with fewer cycles. If OverrideCycles is present in the [BCLConvert_Settings] section, this value must be consistent with the sum of the Read1 section of OverrideCycles."
                },
                "Read2Cycles": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Number of cycles in the second read. Required when running a paired-end sequencing run. Required if Custom Read 2 Primer is set to true on the UI. If OverrideCycles is present in the [BCLConvert_Settings] section, this value must be consistent with the sum of the Read 2 section of OverrideCycles. Ideally, this value should be 26 or greater. However, you can proceed with fewer cycles."
                },
                "Index1Cycles": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Number of cycles in the first Index Read. Required when sequencing more than one sample. If OverrideCycles is present in the [BCLConvert_Settings] section, this value must be consistent with the sum of the Index 1 section of OverrideCycles."
                },
                "Index2Cycles": {
                    "type": "integer",
                    "minimum": 1,
                    "description": "Number of cycles in the first Index Read. Required when sequencing more than one sample. If OverrideCycles is present in the [BCLConvert_Settings] section, this value must be consistent with the sum of the Index 2 section of OverrideCycles."
                }
            }
        },
        "Sequencing_Settings": {
            "type": "object",
            "required": [],
            "properties": {
                "LibraryPrepKits": {
                    "type": "string",
                    "description": "Your library prep kit. Only one library prep kit is allowed."
                }
            }
        },
        "BCLConvert_Settings": {
            "type": "object",
            "required": ["SoftwareVersion"],
            "properties": {
                "AdapterRead1": {
                    "type": "string",
                    "pattern": "^[ACGT]+",
                    "description": "The sequence to trim or mask from the end of Read 1. AdapterRead1 trims cycles by default. Value must be <= Read1Cycles."
                },
                "AdapterRead2": {
                    "type": "string",
                    "pattern": "^[ACGT]+",
                    "description": "The sequence to trim or mask from the end of Read 2. AdapterRead2 trims cycles by default. Value must be <= Read2Cycles."
                },
                "BarcodeMismatchesIndex1": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 2,
                    "default": 1,
                    "description": "The number of allowed mismatches between the first Index Read and index sequence. Only required if Index1Cycles is specified."
                },
                "BarcodeMismatchesIndex2": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 2,
                    "default": 1,
                    "description": "The number of allowed mismatches between the first Index Read and index sequence. Only required if Index2Cycles is specified."
                },
                "FastqCompressionFormat": {
                    "type": "string",
                    "enum": ["dragen", "gzip"]
                },
                "OverrideCycles": {
                    "type": "string",
                    "pattern": "^([NYIU][0-9]+;?){1,}$"
                },
                "SoftwareVersion": {
                    "type": "string",
                    "pattern": "^[0-9]+\.[0-9]+\.[0-9]+.*"
                }
            },
            "BCLConvert_Data": {
                "type": "object",
                "required": ["Sample_ID"],
                "properties": {
                    "Sample_ID": {
                        "type": "string",
                        "pattern": "^[a-zA-Z0-9\-_]+$",
                        "maxLength": 20,
                        "description": "The ID of the sample. Separate each identifier with a dash or underscore.",
                        "examples": ["Sample1-DQB1-022515"]
                    },
                    "Index": {
                        "type": "string",
                        "pattern": "^[ACTG]+$",
                        "description": "The index sequence associated with the sample. Required when sequencing more than one sample."
                    },
                    "Index2": {
                        "type": "string",
                        "pattern": "^[ACTG]+$",
                        "description": "The second index sequence associated with the sample. Make sure the second index (i5) adapter sequences are in forward orientation. DRAGEN automatically reverse complements i5 indexes during secondary analysis."
                    },
                    "Lane": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "The lane of the flow cell. Lanes are represented by one integer value."
                    },
                    "Sample_Project": {
                        "type": "string",
                        "pattern": "^[a-zA-Z0-9\-_]+$",
                        "maxLength": 20
                    }
                }
            }
        }
    }
}
def parse_overrideCycles(cyclestr : str) -> dict:
    def expand(short: str) -> str:
        res = ""
        pt = re.compile("([NYIU]+)([0-9]*);?")
        matches = re.findall(pt, short)
        for letter, freq in matches:
            res += letter * int(freq)
        return res

    cycles = cyclestr.split(";")
    if len(cycles) < 1:
        raise Exception(f"OverrideCycles {cyclestr} cannot be parsed to a cycle sequence.")
    res = {"Read1Cycles": expand(cycles[0])}
    if( len(cycles) == 2 ):
        res['Read2Cycles'] = expand(cycles[1])
    elif( len(cycles) == 3 ):
        res['Index1Cycles'] = expand(cycles[1])
        res['Read2Cycles'] = expand(cycles[2])
    elif( len(cycles) == 4 ):
        res['Index1Cycles'] = expand(cycles[1])
        res['Index2Cycles'] = expand(cycles[2])
        res['Read2Cycles'] = expand(cycles[3])
    elif( len(cycles) == 1 ):
        pass
    else:
        raise Exception(f"OverrideCycles {cyclestr} defines too many elements.")
    return res


def illuminasamplesheetv2logic(doc : SectionedSheet):
    """
    this function checks the logic that is described in
    https://support-docs.illumina.com/IN/NextSeq10002000/Content/SHARE/SampleSheetv2/SampleSheetValidation_fNS_m2000_m1000.htm

    We won't check at the level of the index kits (i.e. that the indices match the kit etc)
    """
    if 'BCLConvert_Settings' in doc:
        if 'OverrideCycles' in doc['BCLConvert_Settings']:
            cycles = parse_overrideCycles(doc['BCLConvert_Settings']['OverrideCycles'])
            for elemname, elemseq in cycles.items():
                if elemname not in doc['Reads']:
                    raise Exception(f"BCLConvert_Settings.OverrideCycles defines {elemname}, but it is not specified in the Reads section")
                if doc['Reads'][elemname] != len(elemseq):
                    raise Exception(f"Reads.{elemname} is {doc['Reads'][elemname]}, but BCLConvert_Settings.OverrideCycles specifies a length of {len(elemseq)}")
            for elemname in [i for i in ['Read1Cycles', 'Read2Cycles', 'Index1Cycles', 'Index2Cycles'] if i in doc.keys()]:
                if elemname not in cycles.keys():
                    raise Exception(f"Reads defines {elemname}, but BCLConvert_Settings.OverrideCycles is incompatible with it.")
        if 'AdapterRead1' in doc['BCLConvert_Settings']:
            if len(doc['BCLConvert_Settings']['AdapterRead1']) > len(doc['Reads']['Read1Cycles']):
                raise Exception(f"BCLConvert_Settings.AdapterRead1 is longer then Reads.Read1Cycles")
        if 'AdapterRead2' in doc['BCLConvert_Settings']:
            if 'Read2Cycles' not in doc['Reads']:
                raise Exception('AdapterRead2 defined in BCLConvert_Settings, but no Read2Cycles entry in Reads')
            if len(doc['BCLConvert_Settings']['AdapterRead2']) > len(doc['Reads']['Read2Cycles']):
                raise Exception("BCLConvert_Settings.AdapterRead2 is longer then Reads.Read2Cycles")
        # The "spec" says: "Only required if Index1Cycles is specified." but this conflicts with an default value of 1
        # so I assume it must be the other way around: if there are Mismatches defined, then this must also be in the Reads section
        if 'BarcodeMismatchesIndex1' in doc['BCLConvert_Settings']:
            if 'Index1Cycles' not in doc['Reads']:
                raise Exception("BCLConvert_Settings defines BarcodeMismatches1, but no Index1Cycles defined in Reads.")
        if 'BarcodeMismatchesIndex2' in doc['BCLConvert_Settings']:
            if 'Index2Cycles' not in doc['Reads']:
                raise Exception("BCLConvert_Settings defines BarcodeMismatches2, but no Index2Cycles defined in Reads.")
    if 'BCLConvert_Data' in doc:
        # Sample_ID do not need to be unique?!
        if( len(doc['BCLConvert_Data']) > 1 ):
            if 'Index' not in doc['BCLConvert_Data'][0]:
                raise Exception("No Index found in BCLConvert_Data, although it contains more than one sample")
            index1 = [i['Index'] for i in doc['BCLConvert_Data']]
            if 'Index2' in doc['BCLConvert_Data'][0]:
                index2 = [i['Index2'] for i in doc['BCLConvert_Data']]
                index = [i1+i2 for i1, i2 in zip(index1, index2)]
            else:
                index = index1
            if len(set(index)) != len(index):
                raise Exception("Indices are not unique.")

def basespacelogic(doc: SectionedSheet):
    if 'Cloud_Data' not in doc:
        raise Exception("no Cloud_Data section")
    if 'BCLConvert_Data' not in doc:
        raise Exception("no BCLConvert_Data section")
    cloud_sample_ids = [i['Sample_ID'] for i in doc['Cloud_Data']]
    bclconvert_sample_ids = [i['Sample_ID'] for i in doc['BCLConvert_Data']]
    for convert_id in bclconvert_sample_ids:
        if convert_id not in cloud_sample_ids:
            raise Exception(f"Sample_ID {convert_id} is defined in the BCLConvert_Data section, but not in the Cloud_Data section.")
    # should we test also for the reverse?



bclconvertschema = {
}

nextseq1k2kschema = {
    "type": "object",
    "required": ["Header", "Reads"],
    "properties": {
        "Reads": {
            "type": "object",
            "properties": {
                "Index1Cycles": {
                    "maximum": 10
                },
                "Index2Cycles": {
                    "maximum": 10
                },
            }
        }
    }
}

class SampleSheetV2:
    def __init__(self, secsheet: SectionedSheet, validation = [illuminasamplesheetv2schema, illuminasamplesheetv2logic]):
        if validation is None:
            schemata = []
        elif type(validation) == list:
            pass
        else:
            validation = [validation]

        for schema in validation:
            if(type(schema) == dict):
                validate(instance=secsheet, schema=schema)
            elif(type(schema) == types.FunctionType):
                schema(secsheet)

        def secname(k):
            secsel = re.compile("^(.*)_(Settings|Data)$")
            m = re.match(secsel, k)
            if m is not None:
                return m.group(1)
            return None

        self.applications = OrderedDict()
        for key in secsheet.keys():
            sectionname = secname(key)
            if key.endswith("_Settings"):
                if sectionname not in self.applications:
                    self.applications[sectionname] = dict()
                self.applications[sectionname]['settings'] = secsheet[key]
            elif key.endswith("_Data"):
                if sectionname not in self.applications:
                    self.applications[sectionname]= dict()
                self.applications[sectionname]['data'] = secsheet[key]
            elif key == 'Header':
                self.header = secsheet['Header']
            elif key == 'Reads':
                self.reads = secsheet['Reads']

    def to_string(self):
        res = ""
        if 'header' in self.__dict__.keys():
            res += '[Header]\n'
            res += settings_to_string(self.header)
        if 'Reads' in self.__dict__.keys():
            res += '[Reads]\n'
            res += settings_to_string(self.reads)
        for appname, app in self.applications.items():
            if 'settings' in app:
                res += f"[{appname}_Settings]\n"
                res += settings_to_string(app['settings'])
            if 'data' in app:
                res += f"[{appname}_Data]\n"
                res += data_to_string(app['data'])
        return(res)