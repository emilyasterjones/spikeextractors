from spikeextractors.extractors.bindatrecordingextractor import BinDatRecordingExtractor
from spikeextractors import RecordingExtractor
import tempfile
from pathlib import Path
from copy import deepcopy
import importlib
import os
import shutil
import json
from .baseextractor import _check_json


class CacheRecordingExtractor(BinDatRecordingExtractor, RecordingExtractor):
    def __init__(self, recording, chunk_size=None):
        RecordingExtractor.__init__(self)  # init tmp folder before constructing BinDatRecordingExtractor
        tmp_folder = self.get_tmp_folder()
        self._recording = recording
        self._tmp_file = tempfile.NamedTemporaryFile(suffix=".dat", dir=tmp_folder).name
        self._is_tmp = True
        dtype = recording.get_traces(start_frame=0, end_frame=2).dtype
        recording.write_to_binary_dat_format(save_path=self._tmp_file, dtype=dtype, chunk_size=chunk_size)
        # keep track of filter status when dumping
        self.is_filtered = self._recording.is_filtered
        BinDatRecordingExtractor.__init__(self, self._tmp_file, numchan=recording.get_num_channels(),
                                          recording_channels=recording.get_channel_ids(),
                                          sampling_frequency=recording.get_sampling_frequency(),
                                          dtype=dtype, is_filtered=self.is_filtered)
        # keep BinDatRecording kwargs
        self._bindat_kwargs = deepcopy(self._kwargs)
        self.set_tmp_folder(tmp_folder)
        self.copy_channel_properties(recording)
        self._kwargs = {'recording': recording, 'chunk_size': chunk_size}

    def __del__(self):
        if self._is_tmp:
            try:
                os.remove(self._tmp_file)
            except Exception as e:
                print("Unable to remove temporary file", e)

    @property
    def filename(self):
        return self._tmp_file

    def save_to_file(self, save_path):
        save_path = Path(save_path)
        if save_path.suffix != '.dat' and save_path.suffix != '.bin':
            save_path = save_path.with_suffix('.dat')
        if not save_path.parent.is_dir():
            os.makedirs(save_path.parent)
        shutil.move(self._tmp_file, str(save_path))
        self._tmp_file = str(save_path)
        self._kwargs['file_path'] = str(Path(self._tmp_file).absolute())
        self._bindat_kwargs['file_path'] = str(Path(self._tmp_file).absolute())
        self._is_tmp = False
        # re-initialize with new file
        print('re-init')
        self = BinDatRecordingExtractor(**self._bindat_kwargs)

    # override to make serialization avoid reloading and saving binary file
    def make_serialized_dict(self, include_properties=None, include_features=None):
        '''
        Makes a nested serialized dictionary out of the extractor. The dictionary be used to re-initialize an
        extractor with spikeextractors.load_extractor_from_dict(dump_dict)

        Returns
        -------
        dump_dict: dict
            Serialized dictionary
        include_properties: list or None
            List of properties to include in the dictionary
        include_features: list or None
            List of features to include in the dictionary
        '''
        class_name = str(BinDatRecordingExtractor).replace("<class '", "").replace("'>", '')
        module = class_name.split('.')[0]
        imported_module = importlib.import_module(module)

        if self._is_tmp:
            print("Warning: dumping a CacheRecordingExtractor. The path to the tmp binary file will be lost in "
                  "further sessions. To prevent this, use the 'CacheRecordingExtractor.save_to_file('path-to-file)' "
                  "function")

        dump_dict = {'class': class_name, 'module': module, 'kwargs': self._bindat_kwargs,
                     'key_properties': self._key_properties, 'version': imported_module.__version__, 'dumpable': True}
        return dump_dict
