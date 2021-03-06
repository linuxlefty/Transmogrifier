import re
import os
import csv
import collections

import plugins.files


class K8SConfigs(object):
    ''' Parses K8S Confirguration files '''

    DIR_NAME_CONFIGMAPS = 'k8s_configmaps'
    DIR_NAME_SECRETS = 'k8s_secrets'
    DIR_METADATA = 'metadata'
    FILE_METADATA_PODS = 'pod_config_map.csv'
    FILE_METADATA_VARS = 'vars.csv'

    CONFIGTYPE_CONFIGMAP = 'cm'
    CONFIGTYPE_SECRET = 'sec'

    REGEXP_VARIABLES = re.compile(r'\${(\w+)}')

    def __init__(self, directory, deserialize=True):
        '''
        directory(str):     The directory to read the configs from
        deserialize(bool):  TRUE  - config will be deserialized to a python object
                            FALSE - config will be kept as a string read from file
        '''
        self.configmaps = dict()
        self.secrets = dict()
        self.pods = collections.defaultdict(list)
        self.rpods = collections.defaultdict(list)  # Stores the reverse of self.pods
        self.variables = collections.defaultdict(list)

        stomp_errors = not deserialize

        for filepath in self._listdir(directory, self.DIR_NAME_CONFIGMAPS):
            self.configmaps.update(self._deserialize(filepath, deserialize, stomp_errors))

        for filepath in self._listdir(directory, self.DIR_NAME_SECRETS):
            self.secrets.update(self._deserialize(filepath, deserialize, stomp_errors))

        with open(os.path.join(directory, self.DIR_METADATA, self.FILE_METADATA_PODS)) as f:
            reader = csv.reader(f, skipinitialspace=True)
            for pod, configfile, configtype in reader:

                is_valid = True
                if configfile not in self.configmaps and configfile not in self.secrets:
                    is_valid = False

                self.pods[pod].append([configfile, configtype, is_valid])
                self.rpods[configfile].append(pod)

        # Sort pods so stuff looks the same
        for member in [self.pods, self.rpods]:
            for key in member.keys():
                member[key] = sorted(member[key])

        # Create variables file
        lines = []
        for variable, filenames in self.variables.items():
            for filename in filenames:
                lines.append('%s,%s,\n' % (filename, variable))
        with open(os.path.join(directory, self.DIR_METADATA, self.FILE_METADATA_VARS), 'w') as f:
            for line in sorted(lines):
                f.write(line)

    def _listdir(self, *parts):
        root = os.path.join(*parts)
        for filename in os.listdir(root):
            yield os.path.join(root, filename)

    def _deserialize(self, filepath, deserialize=True, stomp_error=False):

        ext = os.path.splitext(filepath)[1]
        filename = os.path.split(filepath)[-1]
        is_valid = True

        with open(filepath, 'r') as f:
            content = f.read()

        try:
            result = plugins.files.parse(content, ext)
        except Exception as e:
            is_valid = False
            if stomp_error:
                print('Error in file:%s => %s' % (filepath, e))
            else:
                raise

        variables = self.REGEXP_VARIABLES.findall(content)

        for variable in variables:
            self.variables[variable].append(filename)

        yield (
            filename, (
                result if deserialize else content,
                ext,
                variables,
                is_valid
            )
        )

