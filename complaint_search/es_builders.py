import re
import copy
import abc
from collections import defaultdict, namedtuple
from complaint_search.defaults import PARAMS, DELIMITER

class BaseBuilder(object):
    __metaclass__  = abc.ABCMeta

    # Filters for those with string type
    _OPTIONAL_FILTERS = ("product", "issue", "company", "state", "zip_code", "timely", 
        "company_response", "company_public_response", 
        "consumer_consent_provided", "submitted_via", "tag", "consumer_disputed")

    # Filters for those that need conversion from string to boolean
    _OPTIONAL_FILTERS_STRING_TO_BOOL = ("has_narrative",)

    # Filters that use different names in Elasticsearch
    _OPTIONAL_FILTERS_PARAM_TO_ES_MAP = {
        "product": "product.raw",
        "sub_product": "sub_product.raw",
        "issue": "issue.raw",
        "sub_issue": "sub_issue.raw",
        "company": "company.raw",
        "company_public_response": "company_public_response.raw",
        "consumer_consent_provided": "consumer_consent_provided.raw",
        "consumer_disputed": "consumer_disputed.raw"
    }

    # Filters that have a child and this maps to their child's name
    _OPTIONAL_FILTERS_CHILD_MAP = {
        "product": "sub_product", 
        "issue": "sub_issue"
    }

    def _get_es_name(self, field):
        return self._OPTIONAL_FILTERS_PARAM_TO_ES_MAP.get(field, field)

    def _has_child(self, field):
        return field in self._OPTIONAL_FILTERS_CHILD_MAP

    def _get_child(self, field):
        return self._OPTIONAL_FILTERS_CHILD_MAP.get(field)

    def __init__(self):
        self.params = {}

    def add(self, **kwargs):
        self.params.update(**kwargs)

    @abc.abstractmethod
    def build(self):
         """Method that will build the body dictionary."""

    ## This create all the bool should filter clauses for a field
    ## es_field_name: a field name (to be filtered in ES)
    ## value_list: a list of values to be filtered for this field
    ## with_child: set to true if this field has a child field
    ## es_child_field_name: if with_child is true, this holds the field
    ## name of the child used (to be filtered in ES)
    def _build_bool_should_clauses(self, field):
        es_field_name = self._get_es_name(field)
        value_list = [ 0 if cd.lower() == "no" else 1 for cd in self.params[field] ] \
            if field in self._OPTIONAL_FILTERS_STRING_TO_BOOL else self.params.get(field) 
        if value_list:
            if not self._has_child(field):
                term_list = [ {"terms": {es_field_name: [value]}} 
                    for value in value_list ]
                return {"bool": {"should": term_list}}
            else:
                item_dict = defaultdict(list)
                for v in value_list:
                    v_pair = v.split(DELIMITER)
                    # No child specified
                    if len(v_pair) == 1:
                        # This will initialize empty list for item if not in 
                        # item_dict yet
                        item_dict[v_pair[0]]
                    elif len(v_pair) == 2:
                        # put subproduct into list
                        item_dict[v_pair[0]].append(v_pair[1])

                # Go through item_dict to create filters
                f_list = []
                for item, child in item_dict.iteritems():
                    item_term = {"terms": {es_field_name: [item]}}
                    # Item without any child specified
                    if not child:
                        f_list.append(item_term)
                    else:
                        child_term = {
                            "terms": {
                                self._get_es_name(self._get_child(field)): child
                            }
                        }
                        f_list.append({"and": {"filters": [item_term, child_term]}})

                return {"bool": {"should": f_list}}

    # This creates a dictionary of all filter_clauses, where the keys are the field name
    def _build_filter_clauses(self):
        filter_clauses = {}
        for item in self.params:
            if item in self._OPTIONAL_FILTERS + self._OPTIONAL_FILTERS_STRING_TO_BOOL:
                filter_clauses[item] = self._build_bool_should_clauses(item)
        return filter_clauses

    def _build_date_range_filter(self, date_min, date_max, es_field_name):
        date_clause = {}
        if date_min or date_max:
            date_clause = {"range": {es_field_name: {}}}
            if date_min:
                date_clause["range"][es_field_name]["from"] = date_min
            if date_max:
                date_clause["range"][es_field_name]["to"] = date_max

        return date_clause

class SearchBuilder(BaseBuilder):
    def __init__(self):
        self.params = copy.deepcopy(PARAMS)

    def _build_highlight(self):
        highlight = {
            "require_field_match": False,
            "number_of_fragments": 1,
            "fragment_size": 500
        }
        if self.params.get("field") == "_all":
            highlight["fields"] = {
                "sub_product": {},
                "date_sent_to_company": {},
                "complaint_id": {},
                "consumer_consent_provided": {},
                "date_received": {},
                "state": {},
                "issue": {},
                "company_response": {},
                "zip_code": {},
                "timely": {},
                "product": {},
                "complaint_what_happened": {},
                "company": {},
                "sub_issue": {},
                "tags": {},
                "company_public_response": {},
                "consumer_disputed": {},
                "has_narrative": {},
                "submitted_via": {}
            }

        else:
            highlight["fields"] = { self.params.get("field"): {}}

        return highlight

    def _build_sort(self):
        sort_field_mapping = {
            "relevance": "_score",
            "created_date": "date_received"
        }

        sort_field, sort_order = self.params.get("sort").rsplit("_", 1)
        sort_field = sort_field_mapping.get(sort_field, "_score")
        return [{sort_field: {"order": sort_order}}]

    def build(self):
        search = {
            "from": self.params.get("frm"), 
            "size": self.params.get("size"), 
            "query": {
                "query_string": {
                    "query": "*",
                    "fields": [
                        self.params.get("field")
                    ],
                    "default_operator": "AND"
                }
            }
        }

        # Highlight
        search["highlight"] = self._build_highlight()

        # sort
        search["sort"] = self._build_sort()

        # query
        search_term = self.params.get("search_term")
        if search_term:
            if re.match("^[A-Za-z\d\s]+$", search_term) and \
            not any(keyword in search_term 
                for keyword in ("AND", "OR", "NOT", "TO")):

                # Match Query
                search["query"] = {
                    "match": {
                        self.params.get("field"): {
                            "query": search_term, 
                            "operator": "and"
                        }
                    }
                }

            else: 

                # QueryString Query
                search["query"] = {
                    "query_string": {
                        "query": search_term,
                        "fields": [
                            self.params.get("field")
                        ],
                        "default_operator": "AND"
                    }
                }

        return search

class PostFilterBuilder(BaseBuilder):

    def build(self):
        filter_clauses = self._build_filter_clauses()
        post_filter = {"and": {"filters": []}}

        ## date_received
        date_received = self._build_date_range_filter(
            self.params.get("date_received_min"),
            self.params.get("date_received_max"), 
            "date_received")

        if date_received:
            post_filter["and"]["filters"].append(date_received)

        ## company_received
        company_received = self._build_date_range_filter(
            self.params.get("company_received_min"),
            self.params.get("company_received_max"), 
            "date_sent_to_company")

        if company_received:
            post_filter["and"]["filters"].append(company_received)

        ## Create filter clauses for all other filters
        for item in self.params:
            if item in self._OPTIONAL_FILTERS + self._OPTIONAL_FILTERS_STRING_TO_BOOL:
                post_filter["and"]["filters"].append(filter_clauses[item])

        return post_filter

class AggregationBuilder(BaseBuilder):
    
    _AGG_FIELDS = ('has_narrative', 'company', 'product', 'issue', 'state', 
        'zip_code', 'timely', 'company_response', 'company_public_response',
        'consumer_disputed', 'consumer_consent_provided', 'tag', 'submitted_via')


    def build(self):

        # Build filter clauses for use later
        filter_clauses = self._build_filter_clauses()
        aggs = {}

        # Creating aggregation object for each field above
        for field in self._AGG_FIELDS:
            field_aggs = {
                "filter": {
                    "and": {
                        "filters": [

                        ]
                    }
                }        
            }

            es_field_name = self._OPTIONAL_FILTERS_PARAM_TO_ES_MAP.get(field, field)
            es_child_name = None
            if field in self._OPTIONAL_FILTERS_CHILD_MAP:
                es_child_name = self._OPTIONAL_FILTERS_PARAM_TO_ES_MAP.get(
                    self._OPTIONAL_FILTERS_CHILD_MAP.get(field))
                field_aggs["aggs"] = {
                    field: {
                        "terms": {
                            "field": es_field_name,
                            "size": 0
                        },
                        "aggs": {
                            es_child_name: {
                                "terms": {
                                    "field": es_child_name,
                                    "size": 0
                                }
                            }
                        }
                    }
                }
            else:
                field_aggs["aggs"] = {
                    field: {
                        "terms": {
                            "field": es_field_name,
                            "size": 0
                        }
                    }
                }

            date_filter = self._build_date_range_filter(
                self.params.get("date_received_min"), 
                self.params.get("date_received_max"), "date_received")

            if date_filter:            
                field_aggs["filter"]["and"]["filters"].append(date_filter)

            company_filter = self._build_date_range_filter(
                self.params.get("company_received_min"), 
                self.params.get("company_received_max"), "date_sent_to_company")

            if company_filter:            
                field_aggs["filter"]["and"]["filters"].append(company_filter)
 
            # Add filter clauses to aggregation entries (only those that are not the same as field name)
            for item in self.params:
                if item != field and item in self._OPTIONAL_FILTERS + self._OPTIONAL_FILTERS_STRING_TO_BOOL:
                    field_aggs["filter"]["and"]["filters"].append(filter_clauses[item])

            aggs[field] = field_aggs

        return aggs        

if __name__ == "__main__":
    searchbuilder = SearchBuilder()
    print searchbuilder.build()
    pfbuilder = PostFilterBuilder()
    print pfbuilder.build()
    aggbuilder = AggregationBuilder()
    print aggbuilder.build()

