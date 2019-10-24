import pandas as pd
import pyarrow
import pyarrow.parquet as pq


class ParquetBackend:

    def __init__(self):
        self.cached_path = None
        self.cached_parquet_file = None
        self.cached_stream = None

    def get_file(self, file_system, path):
        if self.cached_path != path:
            if self.cached_stream is not None:
                self.cached_stream.close()
            self.cached_stream = file_system.open(path)
            self.cached_parquet_file = pq.ParquetFile(self.cached_stream)
            self.cached_path = path
        return self.cached_parquet_file

    def schema(self, file_system, path):
        parquet_file = self.get_file(file_system, path)
        pq_schema = parquet_file.schema.to_arrow_schema()
        names = pq_schema.names
        types = pq_schema.types
        result = {'version': '1'}
        var = []
        obs_cat = []
        obs = []
        str_type = pyarrow.lib.string()
        embedding_to_dimensions = {}
        # var names, then obsm names, then obs
        in_obsm = False
        for i in range(len(names)):
            key = names[i]
            if key.startswith('X_') and (
                    key.endswith('_1') or key.endswith('_2') or key.endswith('_3')):  # assume embedding (e.g. X_PCA_1)
                in_obsm = True
                basis = key[0:len(key) - 2]
                dimension = int(key[len(key) - 1:])
                max_dim = embedding_to_dimensions.get(basis, 0)
                if dimension > max_dim:
                    embedding_to_dimensions[basis] = dimension
            elif types[i] == str_type:
                obs_cat.append(key)
            elif in_obsm:
                obs.append(key)
            else:
                var.append(key)

        result['var'] = var
        result['obs'] = obs
        result['obs_cat'] = obs_cat
        result['n_obs'] = parquet_file.metadata.num_rows
        embeddings = []
        for key in embedding_to_dimensions:
            embeddings.append({'name': key, 'dimensions': embedding_to_dimensions[key]})
        result['embeddings'] = embeddings
        return result

    def get_df(self, file_system, path, keys, embedding_key=None, index=False):
        if embedding_key is not None:
            keys = keys + embedding_key['coordinate_columns']
        if index:
            keys = keys + ['index']  # get pandas index

        parquet_file = self.get_file(file_system, path)
        if len(keys) == 0:
            return pd.DataFrame(index=pd.RangeIndex(parquet_file.metadata.num_rows))
        table = parquet_file.read(keys)
        return table.to_pandas()
