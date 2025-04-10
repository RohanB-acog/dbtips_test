import pandas as pd
from target_analyzer import TargetAnalyzer
from helper import get_disease_descendants
import requests
from typing import *
from utils import fetch_all_publications
from datetime import datetime



def parse_target_introduction(api_response):
    """
    Extracts and formats protein information from an API response into JSON.
    """
    if not api_response or 'results' not in api_response or not api_response['results']:
        return {"error": "Invalid or empty API response."}

    result = api_response['results'][0]
    data = {
        "Accession": result.get('primaryAccession', 'N/A'),
        "Protein": result.get('proteinDescription', {}).get('recommendedName', {}).get('fullName', {}).get('value',
                                                                                                           'N/A'),
        "Gene": result.get('genes', [{}])[0].get('geneName', {}).get('value', 'N/A'),
        "Status": result.get('entryType', 'N/A'),
        "Organism": result.get('organism', {}).get('scientificName', 'N/A'),
        "Protein Existence": result.get('proteinExistence', 'N/A'),
        "Annotation Score": result.get('annotationScore', 'N/A')
    }
    return data


def parse_target_description(api_response: dict):
    target_info = api_response['data']['target']
    target_id = target_info['id']
    function_descriptions = " ".join(target_info['functionDescriptions'])

    synonyms_df = pd.DataFrame(target_info['synonyms'])
    uniprot_synonyms = synonyms_df[synonyms_df['source'] == 'uniprot']['label'].tolist()
    synonyms_output = {}
    if uniprot_synonyms:
        synonyms_output['UniProt Synonyms'] = uniprot_synonyms
    else:
        if not synonyms_df.empty:
            any_synonyms = synonyms_df[synonyms_df['source'] == synonyms_df.iloc[0]['source']]['label'].tolist()
            synonyms_output[f"Synonyms from {synonyms_df.iloc[0]['source']}"] = any_synonyms
        else:
            synonyms_output['Synonyms'] = []

    result_json = {
        "Target ID": target_id,
        "Function Descriptions": function_descriptions,
        "Synonyms": synonyms_output
    }

    return result_json


def parse_taxonomy(api_response):
    """
    Extracts organism taxonomy details from an API response and formats them into JSON.
    """
    if 'results' not in api_response or not api_response['results']:
        return {"error": "Invalid or empty API response."}

    result = api_response['results'][0]
    organism_info = result['organism']
    taxon_id = organism_info.get('taxonId', 'N/A')
    scientific_name = organism_info.get('scientificName', 'N/A')
    common_name = organism_info.get('commonName', 'N/A')
    lineage = organism_info.get('lineage', [])

    # taxonomic_identifier_link = f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?id={taxon_id}"
    # lineage_links = [f"https://www.ncbi.nlm.nih.gov/Taxonomy/Browser/wwwtax.cgi?name={term.replace(' ', '+')}" for term in lineage]

    data = {
        "Taxonomic Identifier": taxon_id,
        # "Taxonomic Identifier Link": taxonomic_identifier_link,
        "Organism": f"{scientific_name} ({common_name})",
        "Taxonomic Lineage": lineage,
        # "Taxonomic Lineage Links": lineage_links
    }

    return data


def parse_targetability(response, exact_target):
    key_to_column = {
        "maxClinicalTrialPhase": "Target in clinic",
        "isInMembrane": "Membrane protein",
        "isSecreted": "Secreted protein",
        "hasLigand": "Ligand binder",
        "hasSmallMoleculeBinder": "Small molecule binder",
        "hasPocket": "Predicted pockets",
        "mouseOrthologMaxIdentityPercentage": "Mouse ortholog identity",
        "hasHighQualityChemicalProbes": "Chemical probes",
        "geneticConstraint": "Genetic constraint",
        "mouseKOScore": "Mouse models",
        "geneEssentiality": "Gene essentiality",
        "hasSafetyEvent": "Known safety events",
        "isCancerDriverGene": "Cancer driver gene",
        "paralogMaxIdentityPercentage": "Paralogues",
        "tissueSpecificity": "Tissue specificity",
        "tissueDistribution": "Tissue distribution"
    }

    targets = response['data']['disease']['associatedTargets']

    if targets['count'] == 0:
        return {"error": "No data for targetability found for the given target."}

    target_data = {"Approved Symbol": exact_target, "Prioritisation": {}}
    for key, value in key_to_column.items():
        target_data["Prioritisation"][value] = "no data"

    for target_info in targets['rows']:
        target = target_info['target']
        if target['approvedSymbol'].lower().strip() == exact_target:
            for item in target['prioritisation']['items']:
                key = item['key']
                if key in key_to_column:
                    value = item['value']
                    try:
                        value = float(value)
                    except ValueError:
                        pass
                    target_data["Prioritisation"][key_to_column[key]] = value

            return target_data

    return {"error": f"No exact match found for target '{exact_target}'."}


def parse_tractability(api_response):
    """
    Extracts tractability data for each modality from the API response and formats it into JSON.
    """
    data = api_response['data']['target']['tractability']
    modalities_description = {
        'SM': 'Small molecule',
        'AB': 'Antibody',
        'PR': 'PROTAC',
        'OC': 'Other modalities'
    }
    tractability = {}

    for modality in modalities_description.keys():
        tractability[modalities_description[modality]] = {
            "Items": [],
            "Links": []
        }
    for item in data:
        modality_name = modalities_description[item['modality']]
        modality_data = tractability[modality_name]
        link = item.get('link', '')

        modality_data["Items"].append({
            "Label": item['label'],
            "Value": item['value'],
            "Link": link
        })
    for modality in tractability:
        items = tractability[modality]["Items"]
        items_dict = {item['Label']: {"Value": item['Value'], "Link": item['Link']} for item in items}
        tractability[modality]["Items"] = items_dict

    return tractability

def parse_gene_map(api_response:dict):
    result=api_response.get('data', {}).get('target', {}).get("depMapEssentiality", [])
    return result

def parse_gene_ontology(api_response: dict):
    aspect_mapping = {'F': 'Molecular Function', 'P': 'Biological Process', 'C': 'Cellular Component'}

    ontology_list = []
    for entry in api_response.get('data', {}).get('target', {}).get('geneOntology', []):
        aspect = aspect_mapping.get(entry['aspect'], entry['aspect'])
        term_id = entry['term']['id']

        ontology_list.append({
            'GO ID': term_id,
            'Name': entry['term']['name'],
            'Aspect': aspect,
            'Evidence': entry['evidence'],
            'Gene Product': entry['geneProduct'],
            'Source': entry['source'],
            'Link': f"https://amigo.geneontology.org/amigo/term/{term_id}"
        })
        # Also hyperlink the name with https://amigo.geneontology.org/amigo/term/{term_id} in frontend
    return ontology_list


def parse_mouse_phenotypes(response):
    if not response:
        return {}
    data = response.get('data', {}).get('target', {}).get('mousePhenotypes', [])
    if not data:
        return {}

    records = {}
    for phenotype in data:
        gene_link = f"https://www.informatics.jax.org/marker/{phenotype['targetInModelMgiId']}"
        phenotype_link = f"https://www.ebi.ac.uk/ols4/ontologies/mp/terms?obo_id={phenotype['modelPhenotypeId']}"

        category_links = [f"https://www.ebi.ac.uk/ols4/ontologies/mp/classes?obo_id={cls['id']}" for cls in
                          phenotype.get('modelPhenotypeClasses', [])]
        allelic_composition_links = [f"https://www.informatics.jax.org/allele/genoview/{model['id']}" for model in
                                     phenotype.get('biologicalModels', [])]

        records[phenotype["modelPhenotypeLabel"]] = {
            'Gene': {
                'Name': phenotype['targetInModel'],
                'Link': gene_link
            },
            'Phenotype': {
                'Label': phenotype['modelPhenotypeLabel'],
                'Link': phenotype_link
            },
            'Categories': [{'Label': cls['label'], 'Link': link} for cls, link in
                           zip(phenotype.get('modelPhenotypeClasses', []), category_links)],
            'Allelic Compositions': [{'Composition': model['allelicComposition'], 'Link': link} for model, link in
                                     zip(phenotype.get('biologicalModels', []), allelic_composition_links)]
        }

    return records


def parse_paralogs(results):
    species_codes = {
        "human": "9606",
        "mouse": "10090",
        "worm": "6239",
        "zebrafish": "7955"
    }

    json_output = {}
    for species, content in results.items():
        species_data = []
        for item in content['data']:
            paralog_pair_url = f"https://www.flyrnai.org/tools/paralogs/web/expression/{item['Paralog_PairID']}"
            paralog_data = {
                "Species": species,
                "Species ID": species_codes[species],
                "Gene1 Symbol": item['gene1'],
                "Paralog Score": item['Paralog_Score'],
                "DIOPT Score": item['DIOPT_score'],
                "Paralog Pair URL": paralog_pair_url,
                "Gene2 Symbol": item['gene2'],
                "1-Protein Acc": item['protein1_acc'],
                "2-Protein Acc": item['protein2_acc'],
                "Alignment Length": item['alignment_length'],
                "Identity Score": item['percent_id'],
                "Similarity Score": item['percent_similarity'],
                "Common GO slim": item['common_go_slim'],
                "Common Yeast Paralogs": item['common_sc_orthologs'],
                "Common Fly Paralogs": item['common_dm_orthologs'],
                "Common Protein Interactors": item['common_ppi_count'],
                "Common Genetic Interactors": item['common_gi_count']
            }

            if species == 'human':
                paralog_data.update({
                    "Coexpressed Samples": item.get('coexpressed', '-'),
                    "Tissue Expression Correlation": item.get('tissue_correlation', '-'),
                    "Cell Line Expression Correlation": item.get('cell_line_correlation', '-')
                })

            species_data.append(paralog_data)

        species_data_sorted = sorted(species_data, key=lambda x: float(x['Paralog Score']), reverse=True)
        json_output[species] = species_data_sorted

    return json_output


def parse_protein_expression(expressions):
    """
    Prepare data into a JSON format where each organ has a list of tissues,
    each with corresponding RNA Z-Score and Protein Level.
    """
    organ_data = {}
    for exp in expressions:
        for organ in exp['tissue']['organs']:
            rna_score = max(0, exp['rna']['level'])
            protein_level = max(0, exp['protein']['level'])
            if organ not in organ_data:
                organ_data[organ] = []
            organ_data[organ].append({
                'Tissue': exp['tissue']['label'],
                'RNA Z-Score': rna_score,
                'Protein Level': protein_level
            })

    return {"data": [{organ: tissues} for organ, tissues in organ_data.items()]}


def parse_subcellular(api_response):
    """
    Parses topology data from the subcellular section of a UniProt response and formats it into a list of JSON objects.
    """
    entries = []
    for feature in api_response[0]['features']:
        if feature['category'] == 'TOPOLOGY':
            type_ = feature['type']
            if type_ == 'TOPO_DOM':
                type_name = 'Topological domain'
            elif type_ == 'TRANSMEM':
                type_name = 'Transmembrane'
            else:
                continue

            entry = {
                "Type": type_name,
                "Positions": f"{feature['begin']}-{feature['end']}",
                "Description": feature['description'],
                "Description Link": f"https://www.ebi.ac.uk/QuickGO/term/{feature['evidences'][0]['code']}",
                "Blast Link": f"https://www.uniprot.org/blast?ids={api_response[0]['accession']}[{feature['begin']}-{feature['end']}]"
            }

            entries.append(entry)  # Add the entry to the list

    return entries


def parse_knowndrugs(api_response, disease_list):
    """
    Processes KnownDrugs API response to filter the latest phase entries of drug data 
    and return them as JSON based on a provided list of diseases.
    """
    if not api_response:
        return []
    
    target_id = api_response['data']['target']['id']
    known_drugs = api_response['data']['target']['knownDrugs']

    if known_drugs['count'] == 0:
        return []

    disease_set = set(disease_list)

    def phase_to_number(phase):
        mapping = {
            4: 4,
            3: 3,
            'Phase II': 2,
            'Phase I (Early)': 1.1,
            'Phase I': 1,
            'N/A': 0
        }
        return mapping.get(phase, 0)

    def status_priority(status):
        priorities = {
            'Completed': 8,
            'Terminated': 7,
            'Suspended': 6,
            'Withdrawn': 5,
            'Recruiting': 4,
            'Active, not recruiting': 3,
            'Not yet recruiting': 2,
            'N/A': 1
        }
        return priorities.get(status, -1)

    def get_sponsor_name(url):
        nct_id = url.split('/')[-1] if 'clinicaltrials.gov' in url else None
        if not nct_id:
            return "URL Invalid or Not Applicable"

        api_url = f"https://clinicaltrials.gov/api/int/studies/{nct_id}?history=true"
        try:
            response = requests.get(api_url)
            response_data = response.json()
            sponsor_name = response_data['study']['protocolSection']['identificationModule']['organization']['fullName']
            return sponsor_name
        except Exception as e:
            print(f"Failed to fetch sponsor from {api_url}: {str(e)}")
            return "Unknown"
        
    def check_drug_approval_status(record: Dict[str, Any]) -> str:
        """
        Determines the approval status of a drug based on the given conditions.

        Args:
            record (dict): A dictionary containing the drug record details.
            disease_id (str): The disease ID to match against approved indications.

        Returns:
            str: Returns "Approved" if all conditions are met, otherwise "Not Known".
        """
        # Extract relevant fields
        status: str = record.get("status", "")
        drug: Dict[str, Any] = record.get("drug", {})
        disease_id: str=record.get("disease",{}).get("id","")
        approved_indications: list[str] = drug.get("approvedIndications",[]) or []
        is_approved: bool = drug.get("isApproved", False)
        has_been_withdrawn: bool = drug.get("hasBeenWithdrawn", True)

        # (status == "Completed" or not status)  # Condition 1: Status must be 'Completed' or null/empty
        # Check the conditions
        if (
            (status == "Completed" or not status)
            and is_approved  # Condition 2: isApproved must be True
            and disease_id in approved_indications
            and not has_been_withdrawn  # Condition 4: Drug must not have been withdrawn
        ):
            return "Approved"
        
        return "Not Known"
    
    
    def get_why_stopped(nct_id: str) -> str:
        api_url = f"https://clinicaltrials.gov/api/int/studies/{nct_id}?history=true"

        try:
            # Send a GET request to the API
            response = requests.get(api_url)
            
            # Raise an error if the response code is not 200
            response.raise_for_status()
            
            # Parse the JSON response
            study_data = response.json()
            
            # Extract and return the `whyStopped` field
            return study_data.get("study", {}).get("protocolSection", {}).get("statusModule", {}).get("whyStopped", "")
        
        except requests.RequestException as e:
            print(f"Error fetching data for NCT ID {nct_id}: {e}")
            return ""
        
    
    def get_latest_phase_entries(data):
        temp_entries = {}
        for entry in data:
            if entry['disease']['name'].lower() in disease_set or entry['disease']['id'] in disease_set:
                key = (entry['drug']['id'], entry['disease']['id'])
                phase_num = entry['phase']
                # status_pri = status_priority(entry.get('status', 'N/A'))
                entry_value = (phase_num, entry)

                if key not in temp_entries:
                    temp_entries[key] = [entry_value]
                else:
                    temp_entries[key].append(entry_value)
    
        # filtered_entries = {}
        # for key, values in temp_entries.items():
        #     max_phase = max([v[0] for v in values])
        #     max_phase_entries = [v for v in values if v[0] == max_phase]
        #     highest_priority_entry = max(max_phase_entries, key=lambda x: x[1])
        #     filtered_entries[key] = highest_priority_entry[2]
                

        # return list(filtered_entries.values())
        filtered_entries = {}
        for key, values in temp_entries.items():
            max_phase = max([v[0] for v in values])
            if max_phase<=3:
                max_phase_entries = [v[1] for v in values if v[0] == max_phase]
                filtered_entries[key] = max_phase_entries
            else:
                # when max phase is 4,take all entries with phase 3 and 4
                max_phase_entries = [v[1] for v in values if v[0] == max_phase]
                max_phase_entries_lower=[v[1] for v in values if v[0] == max_phase-1]
                max_phase_entries.extend(max_phase_entries_lower)
                filtered_entries[key] = max_phase_entries
            
        combined_list = []

        # Loop through all lists and extend
        for lst in filtered_entries.values():
            combined_list.extend(lst)
        return combined_list

    latest_phase_entries = get_latest_phase_entries(known_drugs['rows'])
    known_drugs_list = []
    for entry in latest_phase_entries:
        drug_id = entry['drug']['id']
        disease_id = entry['disease']['id']
        urls = entry['urls']
        sponsor = "Unknown"
        why_stopped=""
        if urls:
            for url in urls:
                if url['name'] == 'ClinicalTrials':
                    sponsor = get_sponsor_name(url['url'])
                    nct_id = url['url'].split('/')[-1]
                    why_stopped=get_why_stopped(nct_id=nct_id)
                    break

        known_drugs_list.append({
            "Drug": entry['drug']['name'],
            "Drug URL": f"https://platform.opentargets.org/drug/{drug_id}",
            "Type": entry['drugType'],
            "Mechanism of Action": entry['mechanismOfAction'],
            "Disease": entry['disease']['name'],
            "Disease URL": f"https://platform.opentargets.org/disease/{disease_id}",
            "Phase": f"Phase {entry['phase']}",
            "Status": entry['status'] or 'N/A',
            "Source URLs": [url['url'] for url in entry['urls'] if url['name'] == 'ClinicalTrials'],
            "Sponsor": sponsor,
            "WhyStopped":why_stopped,
            "ApprovalStatus":check_drug_approval_status(entry)
        }
        )
    return known_drugs_list


# def parse_knowndrugs(api_response):
#     """
#     Processes KnownDrugs API response to filter the latest phase entries of drug data and return them as JSON.
#     """
#     target_id = api_response['data']['target']['id']
#     known_drugs = api_response['data']['target']['knownDrugs']

#     if known_drugs['count'] == 0:
#         return []

#     def phase_to_number(phase):
#         mapping = {
#             'Phase IV': 4,
#             'Phase III': 3,
#             'Phase II': 2,
#             'Phase I (Early)': 1.1,
#             'Phase I': 1,
#             'N/A': 0
#         }
#         return mapping.get(phase, 0)

#     def status_priority(status):
#         priorities = {
#             'Completed': 8,
#             'Terminated': 7,
#             'Suspended': 6,
#             'Withdrawn': 5,
#             'Recruiting': 4,
#             'Active, not recruiting': 3,
#             'Not yet recruiting': 2,
#             'N/A': 1
#         }
#         return priorities.get(status, -1)

#     def get_sponsor_name(url):
#         nct_id = url.split('/')[-1] if 'clinicaltrials.gov' in url else None
#         if not nct_id:
#             return "URL Invalid or Not Applicable"

#         api_url = f"https://clinicaltrials.gov/api/int/studies/{nct_id}?history=true"
#         try:
#             response = requests.get(api_url)
#             response_data = response.json()
#             sponsor_name = response_data['study']['protocolSection']['identificationModule']['organization']['fullName']
#             return sponsor_name
#         except Exception as e:
#             print(f"Failed to fetch sponsor from {api_url}: {str(e)}")
#             return "Unknown"

#     def get_latest_phase_entries(data):
#         temp_entries = {}
#         for entry in data:
#             key = (entry['drug']['id'], entry['disease']['id'])
#             phase_num = phase_to_number(entry['phase'])
#             status_pri = status_priority(entry.get('status', 'N/A'))
#             entry_value = (phase_num, status_pri, entry)

#             if key not in temp_entries:
#                 temp_entries[key] = [entry_value]
#             else:
#                 temp_entries[key].append(entry_value)

#         filtered_entries = {}
#         for key, values in temp_entries.items():
#             max_phase = max([v[0] for v in values])
#             max_phase_entries = [v for v in values if v[0] == max_phase]
#             highest_priority_entry = max(max_phase_entries, key=lambda x: x[1])
#             filtered_entries[key] = highest_priority_entry[2]

#         return list(filtered_entries.values())

#     latest_phase_entries = get_latest_phase_entries(known_drugs['rows'])
#     known_drugs_list = []
#     for entry in latest_phase_entries:
#         drug_id = entry['drug']['id']
#         disease_id = entry['disease']['id']
#         urls = entry['urls']
#         sponsor = "Unknown"
#         if urls:
#             for url in urls:
#                 if 'clinicaltrials.gov' in url['url']:
#                     sponsor = get_sponsor_name(url['url'])
#                     break

#         known_drugs_list.append({
#             "Drug": entry['drug']['name'],
#             "Drug URL": f"https://platform.opentargets.org/drug/{drug_id}",
#             "Type": entry['drugType'],
#             "Mechanism of Action": entry['mechanismOfAction'],
#             "Disease": entry['disease']['name'],
#             "Disease URL": f"https://platform.opentargets.org/disease/{disease_id}",
#             "Phase": f"Phase {entry['phase']}",
#             "Status": entry['status'] or 'N/A',
#             "Source URLs": [url['url'] for url in entry['urls']],
#             "Sponsor": sponsor
#         }
#         )
#     return known_drugs_list


def parse_safety_events(api_response):
    safety_liabilities = api_response['data']['target']['safetyLiabilities']

    if not safety_liabilities:
        print("No Safety events found for target")
        return {"error": "No Safety events found for target"}

    entries = []
    for event in safety_liabilities:
        biosystems_links = [
            {
                "tissueLabel": sample["tissueLabel"],
                "tissueLink": f"https://identifiers.org/{sample['tissueId'].replace('_', ':')}"
            }
            for sample in event['biosamples']
        ]

        direction = event['effects'][0]['direction']
        dosing = event['effects'][0]['dosing']
        dosing_effect = {"Direction": direction, "Dosing": dosing}

        event_link = {
            "Event": event['event'],
            "EventLink": f"https://platform.opentargets.org/disease/{event['eventId']}" if event['eventId'] else None
        }

        if event['url']:
            source = {"Source": event["datasource"], "SourceURL": event["url"]}
        elif event['literature']:
            literature_link = f"https://europepmc.org/abstract/med/{event['literature']}"
            source = {"Source": event["datasource"], "SourceURL": literature_link}
        else:
            source = {"Source": event["datasource"], "SourceURL": None}

        entries.append({
            "Safety Event": event_link,
            "Biosystems": biosystems_links,
            "Dosing Effect": dosing_effect,
            "Experimental Studies": event['studies'] if event['studies'] else "N/A",
            "Source": source
        })

    return {"Safety Events": entries}


def fetch_publication_info(literature_id):
    """
    Fetches publication information from Europe PMC for the given literature ID.
    """
    url = f"https://www.ebi.ac.uk/europepmc/webservices/rest/search?query={literature_id}&format=json"
    response = requests.get(url)
    if response.status_code == 200:
        data = response.json()
        if data['hitCount'] > 0:
            publication = data.get('resultList', {}).get('result', [{}])[0]
            # Set default values for each key
            title = publication.get('title', '')
            authors = publication.get('authorString', '')
            year = publication.get('pubYear', '')
            return title, authors, year
        else:
            return None, None, None
    else:
        return None, None, None


def parse_publications(rows, disease_and_id):
    """
    Parses the API response and returns the filtered publication data for specified diseases in the Json format.
    """
    publications = []
    disease_and_id = {key: value.replace(":", "_") for key, value in disease_and_id.items()}

    # rows = api_response.get('data', {}).get('disease', {}).get('europePmc', {}).get('rows', [])
    for row in rows:
        disease = row['disease']['name']
        disease_id = row['disease']['id']

        if disease_id in disease_and_id.values():
            for literature_id in row['literature']:
                title, authors, year = fetch_publication_info(literature_id)

                if title and authors and year:
                    publication_info = {
                        'diseasePhenotype': disease,
                        'disease_id': disease_id,
                        'europePmcId': literature_id,
                        'publication': title,
                        'authors': authors,
                        'year': year
                    }
                    publications.append(publication_info)

    return publications


def fetch_and_parse_publications_for_target(targets_ensembl_ids, diseases_and_efo):
    """
    Fetches and parses publication data for a target and multiple diseases,
    then returns the data in a single list as per the required format.
    """
    final_publications = []
    for disease_name, efo_id in diseases_and_efo.items():
        all_rows: List[Dict[str,Any]] = fetch_all_publications(efo_id,targets_ensembl_ids)
        parsed_data = parse_publications(all_rows, diseases_and_efo)
        if parsed_data:
            final_publications.extend(parsed_data)

    return final_publications


def parse_disease_known_drugs(api_response,disease_exact_synonyms:List[str]):
    """
    Processes DiseaseKnownDrugs API response to first filter for entries with the source as 'ClinicalTrials'.
    Then, it filters the latest phase entries of drug data, considering the highest status in case of phase ties.
    It also fetches the sponsor names from the ClinicalTrials URLs.
    """
    if api_response['data']['disease']['knownDrugs']['count'] == 0:
        return []

    def status_priority(status):
        return {
            'Completed': 8,
            'Terminated': 7,
            'Suspended': 6,
            'Withdrawn': 5,
            'Recruiting': 4,
            'Active, not recruiting': 3,
            'Not yet recruiting': 2,
            'N/A': 1
        }.get(status, -1)

    def get_sponsor_name(nct_id):
        api_url = f"https://clinicaltrials.gov/api/int/studies/{nct_id}?history=true"
        try:
            response = requests.get(api_url,timeout=5)
            response.raise_for_status()
            response_data = response.json()
            sponsor_name = response_data['study']['protocolSection']['identificationModule']['organization']['fullName']
            return sponsor_name
        except Exception as e:
            print(f"Failed to fetch sponsor from {api_url}: {str(e)}")
            return "Unknown"


    def fetch_last_update_date(nct_id: str) -> Optional[str]:
        """
        Fetches the clinical trial data for the given NCT ID and extracts the last update date.

        Args:
            nct_id (str): The NCT ID of the clinical trial.

        Returns:
            Optional[str]: The `lastUpdatePostDateStruct.date` from the API response, or None if not found.
        """
        base_url = f"https://clinicaltrials.gov/api/v2/studies/{nct_id}"
        
        try:
            # Make the API request
            response = requests.get(base_url)
            response.raise_for_status()  # Raise an exception for HTTP errors

            # Parse the JSON response
            api_response = response.json()

            # Extract the last update date
            return api_response.get("protocolSection", {}).get("statusModule", {}).get("lastUpdatePostDateStruct", {}).get("date")
        except requests.exceptions.RequestException as e:
            print(f"HTTP error occurred: {e}")
        except Exception as e:
            print(f"An error occurred: {e}")
        return None

    def extract_nct_ids(data: Dict[str, Any]) -> List[str]:
        """
        Extract NCT IDs from the given data where the name is "ClinicalTrials".

        Args:
            data (Dict[str, Any]): The input data containing a list of URLs.

        Returns:
            List[str]: A list of NCT IDs extracted from the URLs.
        """
        nct_ids: List[str] = []

        # Iterate through the URLs in the data
        for url_entry in data.get("urls", []):
            # Check if the name is "ClinicalTrials"
            if url_entry.get("name") == "ClinicalTrials":
                url: str = url_entry.get("url", "")
                # Extract the NCT ID from the URL
                if "NCT" in url:
                    nct_id = url.split("/")[-1]
                    nct_ids.append(nct_id)

        return nct_ids
    
    def get_latest_phase_entries(data):
        temp_entries = {}
        for entry in data:
            # if any(url['name'] == 'ClinicalTrials' for url in entry['urls']):
            key = (entry['drug']['id'], entry['target']['id'])
            phase_num = entry['phase']
            # status_pri = status_priority(entry['status'])
            entry_value = (phase_num, entry)
            if key not in temp_entries:
                temp_entries[key] = [entry_value]
            else:
                temp_entries[key].append(entry_value)

        filtered_entries = {}
        for key, values in temp_entries.items():
            max_phase = max([v[0] for v in values])
            if max_phase<=3:
                max_phase_entries = [v[1] for v in values if v[0] == max_phase]
                filtered_entries[key] = max_phase_entries
            else:
                # when max phase is 4,take all entries with phase 3 and 4
                max_phase_entries = [v[1] for v in values if v[0] == max_phase]
                max_phase_entries_lower=[v[1] for v in values if v[0] == max_phase-1]
                max_phase_entries.extend(max_phase_entries_lower)
                filtered_entries[key] = max_phase_entries
            
        combined_list = []

        # Loop through all lists and extend
        for lst in filtered_entries.values():
            combined_list.extend(lst)
        return combined_list

    def get_why_stopped(nct_id: str) -> str:
        api_url = f"https://clinicaltrials.gov/api/int/studies/{nct_id}?history=true"

        try:
            # Send a GET request to the API
            response = requests.get(api_url)
            
            # Raise an error if the response code is not 200
            response.raise_for_status()
            
            # Parse the JSON response
            study_data = response.json()
            
            # Extract and return the `whyStopped` field
            return study_data.get("study", {}).get("protocolSection", {}).get("statusModule", {}).get("whyStopped", "")
        
        except requests.RequestException as e:
            print(f"Error fetching data for NCT ID {nct_id}: {e}")
            return ""

    
    def check_drug_approval_status(record: Dict[str, Any], disease_id: str) -> str:
        """
        Determines the approval status of a drug based on the given conditions.

        Args:
            record (dict): A dictionary containing the drug record details.
            disease_id (str): The disease ID to match against approved indications.

        Returns:
            str: Returns "Approved" if all conditions are met, otherwise "Not Known".
        """
        # Extract relevant fields
        status: str = record.get("status", "")
        drug: Dict[str, Any] = record.get("drug", {})
        is_approved: bool = drug.get("isApproved", False)
        approved_indications: list[str] = drug.get("approvedIndications") or []
        has_been_withdrawn: bool = drug.get("hasBeenWithdrawn", True)

        # (status == "Completed" or not status)  # Condition 1: Status must be 'Completed' or null/empty
        
        # Check the conditions
        if (
            (status == "Completed" or not status)
            and is_approved  # Condition 2: isApproved must be True
            and disease_id in approved_indications  # Condition 3: Disease ID must be in approved indications
            and not has_been_withdrawn  # Condition 4: Drug must not have been withdrawn
        ):
            return "Approved"
        
        return "Not Known"
    
    exact_synonyms_row=[]
    for row in api_response['data']['disease']['knownDrugs']['rows']:
        if row.get("disease",{}).get("name","").lower() in disease_exact_synonyms:
            exact_synonyms_row.append(row)
    latest_phase_entries = get_latest_phase_entries(exact_synonyms_row)
    efo_id_disease=api_response['data']['disease']['id']
    known_drugs_list = []
    for entry in latest_phase_entries:
        sponsor = "Unknown"
        why_stopped=""
        for url in entry['urls']:
            if url['name'] == 'ClinicalTrials':
                nct_id = url['url'].split('/')[-1]
                sponsor = get_sponsor_name(nct_id)
                why_stopped=get_why_stopped(nct_id=nct_id)
                break

        known_drugs_list.append({
            "Disease": entry['disease']['name'],
            "Disease URL": f"https://platform.opentargets.org/disease/{entry['disease']['id']}",
            "Drug": entry['drug']['name'],
            "Drug URL": f"https://platform.opentargets.org/drug/{entry['drug']['id']}",
            "Type": entry['drugType'],
            "Mechanism of Action": entry['mechanismOfAction'],
            "Phase": f"Phase {1 if entry['phase'] == 0.5 else entry['phase']}",
            "Status": entry['status'],
            "Target": entry['target']['approvedSymbol'],
            "Target URL": f"https://platform.opentargets.org/target/{entry['target']['id']}",
            "Source URLs": [url['url'] for url in entry['urls'] if url['name'] == 'ClinicalTrials'],
            "Sponsor": sponsor,
            "WhyStopped":why_stopped,
            "ApprovalStatus":check_drug_approval_status(entry,efo_id_disease)
        })

    return known_drugs_list


def fetch_and_parse_diseases_known_drugs(diseases,disease_exact_synonyms:Dict[str,Any]) -> Dict[str, Any]:
    """
    Fetch and parse known drug data for a list of diseases specified by their names using an instance of TargetAnalyzer.
    """
    results = {}

    for disease_name in diseases:
        try:
            api_response = TargetAnalyzer.get_disease_knowndrugs(disease_name)
            if api_response and 'data' in api_response:
                parsed_data = parse_disease_known_drugs(api_response,disease_exact_synonyms[disease_name])
                results[disease_name] = parsed_data
            else:
                results[disease_name] = "No data available for this disease"
        except Exception as e:
            results[disease_name] = f"Error fetching data: {str(e)}"
            print(f"Error fetching data: {str(e)}")

    return results


def parse_disease_association(target):
    """Calculate association scores for all data sources and return formatted dictionary for API response."""
    try:
        ALL_DATA_SOURCES = [
            "ot_genetics_portal", "gene_burden", "eva", "genomics_england", "gene2phenotype",
            "uniprot_literature", "uniprot_variants", "orphanet", "clingen", "cancer_gene_census",
            "intogen", "eva_somatic", "cancer_biomarkers", "chembl", "crispr_screen", "crispr",
            "slapenrich", "progeny", "reactome", "sysbio", "europepmc", "expression_atlas",
            "impc", "ot_crispr_validation", "ot_crispr", "encore"
        ]
        response = TargetAnalyzer(target).get_associated_diseases()
        if 'errors' in response:
            raise ValueError(f"API errors encountered: {response['errors']}")

        all_data = []
        selected_diseases = ["Systemic Scleroderma", "Atopic Dermatitis", "Hidradenitis Suppurativa"]
        TARGET_DISEASES = {
            'Hidradenitis Suppurativa': 'EFO_1000710',
            'Systemic Scleroderma': 'EFO_0000717',
            'Atopic Dermatitis': 'MONDO_0011292'
        }

        for disease in selected_diseases:
            parent_efo_id = TARGET_DISEASES[disease]
            descendants_efo_ids = get_disease_descendants(disease)
            descendants_efo_ids.append(parent_efo_id)
            efo_ids_set = set(descendants_efo_ids)

            filtered_associations = [d for d in response['data']['target']['associatedDiseases']['rows'] if
                                     d['disease']['id'] in efo_ids_set]
            for disease_info in filtered_associations:
                data_source_scores = {source: 0 for source in ALL_DATA_SOURCES}
                data_source_scores.update(
                    {ds['componentId']: ds['score'] for ds in disease_info.get('datasourceScores', [])})

                disease_entry = {
                    "disease_name": disease_info['disease']['name'],
                    "disease_id": disease_info['disease']['id'],
                    "Overall Association Score": disease_info['score'],
                    "data sources": data_source_scores
                }
                all_data.append(disease_entry)

        return all_data

    except Exception as e:
        return {"error": str(e)}


def fetch_disease_profile(diseases_and_id):
    """
    Fetches descriptions and synonyms for each disease and returns formatted response.

    Returns:
    dict: A dictionary structured by disease names with their respective descriptions and synonyms.
    """

    results = {}

    for disease_name, id in diseases_and_id.items():
        id = id.replace(":", "_")
        api_url = f"https://www.ebi.ac.uk/ols4/api/v2/ontologies/efo/classes/http%253A%252F%252Fpurl.obolibrary.org%252Fobo%252F{id}?includeObsoleteEntities=true"

        try:
            response = requests.get(api_url)
            response.raise_for_status()
            data = response.json()

            definition = data.get('definition', {})
            if isinstance(definition, dict):
                description = definition.get('value', "No description available")
            elif isinstance(definition, list):
                description = next((item['value'] for item in definition if 'value' in item),
                                   "No description available")
            else:
                description = "Unexpected data format for definition"

            synonyms = data.get('synonym', ["No synonyms available"])

            results[disease_name] = {
                'description': description,
                'synonyms': synonyms
            }
        except requests.RequestException as e:
            results[disease_name] = {
                'description': "Error fetching data",
                'synonyms': f"Error: {str(e)}"
            }

    return results

# if __name__ == "__main__":
#     target = "ADORA3"
#     analyzer = TargetAnalyzer(target)
#     response = analyzer.get_safety()
#     data = parse_safety_events(response)
#     print(data)
#     print("Length : ",len(data))
