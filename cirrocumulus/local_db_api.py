import json
import os


def create_dataset_meta(path):
    result = {'id': path, 'url': path, 'name': os.path.splitext(os.path.basename(path))[0]}
    if os.path.basename(path).endswith('.json'):
        with open(path, 'rt') as f:
            result.update(json.load(f))
    return result


def write_json(json_data, json_path):
    with open(json_path, 'wt') as f:
        json.dump(json_data, f)


class LocalDbAPI:

    def __init__(self, paths):
        self.dataset_to_info = {}  # json_data, meta, json_path

        for path in paths:
            json_data = {}
            basename = os.path.splitext(path)[0]
            old_path = basename + '_filters.json'
            json_path = basename + '.json'
            if os.path.exists(old_path) and os.path.getsize(old_path) > 0:
                with open(old_path, 'rt') as f:
                    json_data['filters'] = json.load(f)

            if os.path.exists(json_path) and os.path.getsize(json_path) > 0:
                with open(json_path, 'rt') as f:
                    json_data.update(json.load(f))
            meta = create_dataset_meta(path)
            if 'filters' not in json_data:
                json_data['filters'] = {}
            if 'categories' not in json_data:
                json_data['categories'] = {}
            self.dataset_to_info[path] = dict(json_data=json_data, meta=meta, json_path=json_path)

    def server(self):
        return dict(mode='client')

    def user(self, email):
        return dict()

    def datasets(self, email):
        results = []
        for key in self.dataset_to_info:
            results.append(self.dataset_to_info[key]['meta'])
        return results

    def get_dataset(self, email, dataset_id, ensure_owner=False):
        result = self.dataset_to_info[dataset_id]['meta']
        result['id'] = dataset_id
        return result

    def category_names(self, email, dataset_id):
        results = []
        json_data = self.dataset_to_info[dataset_id]['json_data']
        categories = json_data['categories']
        for category_name in categories:
            category = categories[category_name]
            for category_key in category:
                r = dict(category=category_name, original=category_key, new=category[category_key]['new'])
                results.append(r)
        return results

    def upsert_category_name(self, email, category, dataset_id, original_name, new_name):
        json_data = self.dataset_to_info[dataset_id]['json_data']
        category_entity = json_data['categories'].get(category)
        if category_entity is None:
            category_entity = {}
            json_data['categories'][category] = category_entity
        if new_name == '':
            if original_name in category_entity:
                del category_entity[original_name]
        else:
            entity = dict(new=new_name)
            category_entity[original_name] = entity
            if dataset_id is not None:
                entity['dataset_id'] = dataset_id
            if email is not None:
                entity['email'] = email
        write_json(json_data, self.dataset_to_info[dataset_id]['json_path'])

    def dataset_filters(self, email, dataset_id):
        json_data = self.dataset_to_info[dataset_id]['json_data']
        results = []
        filters = json_data['filters']
        for key in filters:
            r = filters[key]
            r['id'] = key
            results.append(r)
        return results

    def delete_dataset_filter(self, email, dataset_id, filter_id):
        json_data = self.dataset_to_info[dataset_id]['json_data']
        del json_data['filters'][filter_id]
        write_json(json_data, self.dataset_to_info[dataset_id]['json_path'])

    def get_dataset_filter(self, email, dataset_id, filter_id):
        json_data = self.dataset_to_info[dataset_id]['json_data']
        return json_data['filters'][filter_id]

    def upsert_dataset_filter(self, email, dataset_id, filter_id, filter_name, filter_notes, dataset_filter):
        if filter_id is None:
            import uuid
            filter_id = str(uuid.uuid4())
        json_data = self.dataset_to_info[dataset_id]['json_data']
        entity = json_data['filters'].get(filter_id)
        if entity is None:
            entity = {}
            json_data['filters'][filter_id] = entity
        if filter_name is not None:
            entity['name'] = filter_name
        if dataset_filter is not None:
            entity['value'] = json.dumps(dataset_filter)
        if email is not None:
            entity['email'] = email
        if dataset_id is not None:
            entity['dataset_id'] = dataset_id
        if filter_notes is not None:
            entity['notes'] = filter_notes
        write_json(json_data, self.dataset_to_info[dataset_id]['json_path'])
        return filter_id
