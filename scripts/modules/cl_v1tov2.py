#######################################
#
# Module to convert v1 checklist files
#   to v2.
#
#######################################

# Dependencies
import sys
import yaml
import json
import os
from pathlib import Path

# Get the standard service name from the service dictionary
def get_standard_service_name(service_name, service_dictionary=None):
    svc_match_found = False
    if service_dictionary:
        for svc in service_dictionary:
            if service_name in svc['names']:
                svc_match_found = True
                return svc['service']
        if not svc_match_found:
            return service_name
    else:
        return service_name

# Function to modify yaml.dump for multiline strings, see https://github.com/yaml/pyyaml/issues/240
def str_presenter(dumper, data):
    if data.count('\n') > 0:
        data = "\n".join([line.rstrip() for line in data.splitlines()])  # Remove any trailing spaces, then put it back together again
        return dumper.represent_scalar('tag:yaml.org,2002:str', data, style='|')
    return dumper.represent_scalar('tag:yaml.org,2002:str', data)

# Function that returns a data structure with the objects in v2 format
def generate_v2(input_file, service_dictionary=None, labels=None, id_label=None, cat_label=None, subcat_label=None, verbose=False):
    if verbose: print("DEBUG: Converting file", input_file)
    # Default values for non-mandatory labels
    if not id_label: id_label = 'id'
    if not cat_label: cat_label = 'area'
    if not subcat_label: subcat_label = 'subarea'
    try:
        with open(input_file) as f:
            checklist = json.load(f)
        if 'items' in checklist:
            if verbose: print("DEBUG: {0} items found in JSON file {1}".format(len(checklist['items']), input_file))
            # Create a list of objects in v2 format
            v2recos = []
            for item in checklist['items']:
                # Create a dictionary with the v2 object
                v2reco = {}
                if 'guid' in item:
                    v2reco['guid'] = item['guid']
                if 'text' in item:
                    v2reco['title'] = item['text']
                if 'description' in item:
                    v2reco['description'] = item['description']
                if 'waf' in item:
                    v2reco['waf'] = item['waf']
                if 'severity' in item:
                    if item['severity'].lower() == 'high':
                        v2reco['severity'] = 0
                    elif item['severity'].lower() == 'medium':
                        v2reco['severity'] = 1
                    elif item['severity'].lower() == 'low':
                        v2reco['severity'] = 2
                # Labels
                v2reco['labels'] = {}
                if 'category' in item:
                    v2reco['labels'][cat_label] = item['category']
                if 'subcategory' in item:
                    v2reco['labels'][subcat_label] = item['subcategory']
                if 'id' in item:
                    v2reco['labels'][id_label] = item['id']
                v2reco['queries'] = []
                if 'graph' in item:
                    v2reco['queries'] = {}
                    v2reco['queries']['arg'] = item['graph']
                # Links
                v2reco['links'] = []
                if 'link' in item:
                    v2reco['links'].append(item['link'])
                if 'training' in item:
                    v2reco['links'].append(item['training'])
                # Source
                if 'source' in item:
                    if item['source'].lower() == 'aprl' or item['source'].lower() == 'wafsg':
                        v2reco['source'] = {'type': item['source'].lower()}
                    elif '.yaml' in item['source']:   # If it was imported from YAML it is coming from APRL
                        v2reco['source'] = {'type': 'aprl'}
                    elif '.md' in item['source']:   # If it was imported from Markdown it is coming from a WAF service guide
                        v2reco['source'] = {'type': 'wafsg'}
                elif 'sourceType' in item:
                    v2reco['source'] = {'type': item['sourceType'].lower()}
                    if 'sourceFile' in item:
                        v2reco['source']['file'] = item['sourceFile']
                else:
                    v2reco['source'] = {'type': 'local', 'file': input_file}
                # Service and resource types
                if 'service' in item:
                    v2reco['service'] = get_standard_service_name(item['service'], service_dictionary=service_dictionary)
                v2reco['resourceTypes'] = []
                if 'recommendationResourceType' in item:
                    v2reco['resourceTypes'].append(item['recommendationResourceType'])
                # Else try to get the svc from the service dictionary
                else:
                    if service_dictionary:
                        for svc in service_dictionary:
                            if item['service'] in svc['names']:
                                v2reco['resourceTypes'].append(svc['arm'])
                # If additional labels were specified as parameter, add them to the object
                if labels:
                    for key in labels.keys():
                        v2reco['labels'][key] = labels[key]
                # Add to the list of v2 objects
                v2recos.append(v2reco)
            return v2recos
        else:
            print("ERROR: No items found in JSON file", input_file)
            return None
    except Exception as e:
        print("ERROR: Error when processing JSON file, nothing changed", input_file, ":", str(e))
        return None

# Function that removes empty directories
def remove_empty_dirs(path):
    for root, dirnames, filenames in os.walk(path, topdown=False):
        for dirname in dirnames:
            remove_empty_dirs(os.path.realpath(os.path.join(root, dirname)))

# Function that stores an object generated by generate_v2 in files in the output folder
def store_v2(output_folder, checklist, output_format='yaml', overwrite=False, verbose=False):
    if verbose: print("DEBUG: Storing v2 objects in folder", output_folder)
    # Create the output folder if it doesn't exist
    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    # Add representer to yaml for multiline strings, see https://github.com/yaml/pyyaml/issues/240
    yaml.add_representer(str, str_presenter)
    yaml.representer.SafeRepresenter.add_representer(str, str_presenter) # to use with safe_dum
    # Store each object in a separate YAML file
    for item in checklist:
        # ToDo: create folder structure for the output files:
        #   output_folder/service/waf_pillar/recos.yaml
        if 'guid' in item:
            # Append service and WAF pillar to output folder if available
            this_output_folder = output_folder
            if 'service' in item:
                this_output_folder = os.path.join(output_folder, item['service'].replace(" ", ""))
            else:
                this_output_folder = os.path.join(output_folder, "cross-service")
            if 'waf' in item:
                this_output_folder = os.path.join(this_output_folder, item['waf'].replace(" ", ""))
            # Create the output folder if it doesn't exist
            if not os.path.exists(this_output_folder):
                os.makedirs(this_output_folder)
            # Export JSON or YAML, depending on the output format
            if output_format in ['yaml', 'yml']:
                output_file = os.path.join(this_output_folder, item['guid'] + ".yaml")
                files = list(Path(output_folder).rglob(item['guid'] + ".yaml"))
                # File already exists somewhere in the output folder
                if len(files) > 0:
                    if overwrite:
                        files[0].unlink()
                        with open(output_file, 'w') as f:
                            yaml.dump(item, f)
                        if verbose: print("DEBUG: Stored YAML recommendation in", output_file)
                    else:
                        print("ERROR: File {0} already exists for recommendation, skipping".format(files[0].resolve()))
                        continue
                else:
                    with open(output_file, 'w') as f:
                        yaml.dump(item, f)
                    if verbose: print("DEBUG: Stored YAML recommendation in", output_file)
            elif output_format == 'json':
                output_file = os.path.join(this_output_folder, item['guid'] + ".json")
                files = list(Path(output_folder).rglob(item['guid'] + ".json"))
                # File already exists somewhere in the output folder
                if len(files) > 0:
                    if overwrite:
                        files[0].unlink()
                        with open(output_file, 'w') as f:
                            json.dump(item, f)
                        if verbose: print("DEBUG: Stored JSON recommendation in", output_file)
                    else:
                        print("ERROR: File {0} already exists for recommendation, skipping".format(files[0].resolve()))
                        continue
                else:
                    with open(output_file, 'w') as f:
                        json.dump(item, f)
                    if verbose: print("DEBUG: Stored JSON recommendation in", output_file)
            else:
                print("ERROR: Unsupported output format", output_format)
                sys.exit(1)
        else:
            print("ERROR: No GUID found in recommendation, skipping", item['text'])
            continue
    # Clean up all empty folders that might exist in the output folder, recursively
    if overwrite:
        try:
            if verbose: print("DEBUG: Removing empty directories in output folder", output_folder)
            [os.removedirs(p) for p in Path(output_folder).glob('**/*') if p.is_dir() and len(list(p.iterdir())) == 0]
        except Exception as e:
            print("ERROR: Error when removing empty directories in output folder", output_folder, ":", str(e))
