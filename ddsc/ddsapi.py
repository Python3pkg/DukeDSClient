"""DataServiceApi - communicates with to Duke Data Service REST API."""
import json
import requests

# Swift is currently configured for 5MB file upload chunk size.
SWIFT_BYTES_PER_CHUNK = 5242880


class ContentType(object):
    """
    Contains the types of content for use with http headers.
    """
    json = 'application/json'
    form = 'application/x-www-form-urlencoded'


class KindType(object):
    """
    Holds the types of files supported by DDS.
    """
    file_str = 'dds-file'
    folder_str = 'dds-folder'
    project_str = 'dds-project'

    @staticmethod
    def is_file(item):
        return item.kind == KindType.file_str

    @staticmethod
    def is_folder(item):
        return item.kind == KindType.folder_str

    @staticmethod
    def is_project(item):
        return item.kind == KindType.project_str


class DataServiceApi(object):
    """
    Sends json messages and receives responses back from Duke Data Service api.
    See https://github.com/Duke-Translational-Bioinformatics/duke-data-service.
    Should be eventually replaced by https://github.com/Duke-Translational-Bioinformatics/duke-data-service-pythonClient.
    """
    def __init__(self, auth, url, http=requests):
        """
        Setup for REST api.
        :param auth: str auth token to be send via Authorization header
        :param url: str root url of the data service
        :param http: object requests style http object to do get/post/put
        """
        self.auth = auth
        self.base_url = url
        self.bytes_per_chunk = SWIFT_BYTES_PER_CHUNK
        self.http = http

    def _url_parts(self, url_suffix, url_data, content_type):
        """
        Format the url data based on config_type.
        :param url_suffix: str URL path we are sending a GET/POST/PUT to
        :param url_data: object data we are sending
        :param content_type: str from ContentType that determines how we format the data
        :return: complete url, formatted data, and headers for sending
        """
        url = self.base_url + url_suffix
        send_data = url_data
        if content_type == ContentType.json:
            send_data = json.dumps(url_data)
        headers = {
            'Content-Type': content_type,
            'Authorization': self.auth
        }
        return url, send_data, headers

    def _post(self, url_suffix, post_data, content_type=ContentType.json):
        """
        Send POST request to API at url_suffix with post_data.
        :param url_suffix: str URL path we are sending a POST to
        :param url_data: object data we are sending
        :param content_type: str from ContentType that determines how we format the data
        :return: requests.Response containing the result
        """
        (url, data_str, headers) = self._url_parts(url_suffix, post_data, content_type=content_type)
        resp = self.http.post(url, data_str, headers=headers)
        return self._check_err(resp, url_suffix, post_data)

    def _put(self, url_suffix, put_data, content_type=ContentType.json):
        """
        Send PUT request to API at url_suffix with post_data.
        :param url_suffix: str URL path we are sending a PUT to
        :param url_data: object data we are sending
        :param content_type: str from ContentType that determines how we format the data
        :return: requests.Response containing the result
        """
        (url, data_str, headers) = self._url_parts(url_suffix, put_data, content_type=content_type)
        resp = self.http.put(url, data_str, headers=headers)
        return self._check_err(resp, url_suffix, put_data)

    def _get(self, url_suffix, get_data, content_type=ContentType.json):
        """
        Send GET request to API at url_suffix with post_data.
        :param url_suffix: str URL path we are sending a GET to
        :param url_data: object data we are sending
        :param content_type: str from ContentType that determines how we format the data
        :return: requests.Response containing the result
        """
        (url, data_str, headers) = self._url_parts(url_suffix, get_data, content_type=content_type)
        resp = self.http.get(url, headers=headers, params=data_str)
        return self._check_err(resp, url_suffix, get_data)

    def _check_err(self, resp, url_suffix, data):
        """
        Raise DataServiceError if the response wasn't successful.
        :param resp: requests.Response back from the request
        :param url_suffix: str url to include in an error message
        :param data: data payload we sent
        :return: requests.Response containing the successful result
        """
        if resp.status_code != 200 and resp.status_code != 201:
            raise DataServiceError(resp, url_suffix, data)
        return resp

    def create_project(self, project_name, desc):
        """
        Send POST to /projects creating a new project with the specified name and desc.
        Raises DataServiceError on error.
        :param project_name: str name of the project
        :param desc: str description of the project
        :return: requests.Response containing the successful result
        """
        data = {
            "name": project_name,
            "description": desc
        }
        return self._post("/projects", data)

    def get_projects(self):
        """
        Send GET to /projects returning a list of all projects for the current user.
        Raises DataServiceError on error.
        :return: requests.Response containing the successful result
        """
        return self._get("/projects", {})

    def create_folder(self, folder_name, parent_kind_str, parent_uuid):
        """
        Send POST to /folders to create a new folder with specified name and parent.
        :param folder_name: str name of the new folder
        :param parent_kind_str: str type of parent folder has(dds-folder,dds-project)
        :param parent_uuid: str uuid of the parent object
        :return: requests.Response containing the successful result
        """
        data = {
            'name': folder_name,
            'parent': {
                'kind': parent_kind_str,
                'id': parent_uuid
            }
        }
        return self._post("/folders", data)

    def get_project_children(self, project_id, name_contains):
        """
        Send GET to /projects/{project_id} filtering by a name.
        :param project_id: str uuid of the project
        :param name_contains: str name to filter folders by
        :return: requests.Response containing the successful result
        """
        return self._get_children('projects', project_id, name_contains)

    def get_folder_children(self, folder_id, name_contains):
        """
        Send GET to /folders/{folder_id} filtering by a name.
        :param folder_id: str uuid of the folder
        :param name_contains: str name to filter children by
        :return: requests.Response containing the successful result
        """
        return self._get_children('folders', folder_id, name_contains)

    def _get_children(self, parent_name, parent_id, name_contains):
        data = {
            'name_contains': name_contains
        }
        return self._get("/" + parent_name + "/" + parent_id + "/children", data)

    def create_upload(self, project_id, filename, content_type, size,
                      hash_value, hash_alg):
        """
        Post to /projects/{project_id}/uploads to create a uuid for uploading chunks.
        :param project_id: str uuid of the project we are uploading data for.
        :param filename: str name of the file we want to upload
        :param content_type: str mime type of the file
        :param size: int size of the file in bytes
        :param hash_value: str hash value of the entire file
        :param hash_alg: str algorithm used to create hash_value
        :return: requests.Response containing the successful result
        """
        data = {
            "name": filename,
            "content_type": content_type,
            "size": size,
            "hash": {
                "value": hash_value,
                "algorithm": hash_alg
            }
        }
        return self._post("/projects/" + project_id + "/uploads", data)

    def create_upload_url(self, upload_id, number, size, hash_value, hash_alg):
        """
        Given an upload created by create_upload retrieve a url where we can upload a chunk.
        :param upload_id: uuid of the upload
        :param number: int incrementing number of the upload
        :param size: int size of the chunk in bytes
        :param hash_value: str hash value of chunk
        :param hash_alg: str algorithm used to create hash
        :return: requests.Response containing the successful result
        """
        data = {
            "number": number,
            "size": size,
            "hash": {
                "value": hash_value,
                "algorithm": hash_alg
            }
        }
        return self._put("/uploads/" + upload_id + "/chunks", data)

    def complete_upload(self, upload_id):
        """
        Mark the upload we created in create_upload complete.
        :param upload_id: str uuid of the upload to complete.
        :return: requests.Response containing the successful result
        """
        return self._put("/uploads/" + upload_id + "/complete", {})

    def create_file(self, parent_kind, parent_id, upload_id):
        """
        Create a new file after completing an upload.
        :param parent_kind: str kind of parent(dds-folder,dds-project)
        :param parent_id: str uuid of parent
        :param upload_id: str uuid of complete upload
        :return: requests.Response containing the successful result
        """
        data = {
            "parent": {
                "kind": parent_kind,
                "id": parent_id
            },
            "upload": {
                "id": upload_id
            }
        }
        return self._post("/files/", data)

    def send_external(self, http_verb, host, url, http_headers, chunk):
        """
        Used with create_upload_url to send a chunk the the possibly external object store.
        :param http_verb: str PUT or POST
        :param host: str host we are sending the chunk to
        :param url: str url to use when sending
        :param http_headers: object headers to send with the request
        :param chunk: content to send
        :return: requests.Response containing the successful result
        """
        if http_verb == 'PUT':
            return requests.put(host + url, data=chunk, headers=http_headers)
        elif http_verb == 'POST':
            return requests.post(host + url, data=chunk, headers=http_headers)
        else:
            raise ValueError("Unsupported http_verb:" + http_verb)

    def get_users_by_full_name(self, full_name):
        """
        Send GET request to /users filtering by those full name contains full_name.
        :param full_name: str name of the user we are searching for
        :return: requests.Response containing the successful result
        """
        data = {
            "full_name_contains": full_name,
        }
        return self._get('/users', data, content_type=ContentType.form)

    def get_users_by_page_and_offset(self, page, per_page):
        """
        Send GET request to /users filtering by those full name contains full_name.
        :param page: which page of the users list do we want
        :param per_page: how many items should be on each page
        :return: requests.Response containing the successful result
        """
        data = {
            "page": page,
            "per_page": per_page,
        }
        return self._get('/users', data, content_type=ContentType.form)

    def set_user_project_permission(self, project_id, user_id, auth_role):
        """
        Send PUT request to /projects/{project_id}/permissions/{user_id/ with auth_role value.
        :param project_id: str uuid of the project
        :param user_id: str uuid of the user
        :param auth_role: str project role eg 'project_admin'
        :return: requests.Response containing the successful result
        """
        put_data = {
            "auth_role[id]": auth_role
        }
        return self._put("/projects/" + project_id + "/permissions/" + user_id, put_data,
                         content_type=ContentType.form)

    def get_file(self, file_id):
        """
        Send GET request to /files/{file_id} to retrieve file info.
        :param file_id: str uuid of the file we want info about
        :return: requests.Response containing the successful result
        """
        return self._get('/files/' + file_id, {})


class DataServiceError(Exception):
    """
    Error that wraps up info about it and creates an informative string.
    """
    def __init__(self, response, url_suffix, request_data):
        """
        Create exception for failed response.
        :param response: requests.Response response that was in error
        :param url_suffix: str url we were trying to connect to
        :param request_data: object data we were sending to url
        """
        resp_json = response.json()
        if response.status_code == 500:
            if not resp_json.get('reason'):
                resp_json = {'reason':'Internal Server Error', 'suggestion':'Contact DDS support.'}
        Exception.__init__(self,'Error {} on {} Reason:{} Suggestion:{}'.format(
            response.status_code, url_suffix, resp_json.get('reason',resp_json.get('error','')), resp_json.get('suggestion','')
        ))
        self.response = resp_json
        self.url_suffix = url_suffix
        self.request_data = request_data
