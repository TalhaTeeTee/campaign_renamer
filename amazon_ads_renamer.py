import streamlit as st
import pandas as pd
from collections import defaultdict
from io import BytesIO

# Page configuration
st.set_page_config(
    page_title="Amazon Ads Campaign Renamer",
    page_icon="📊",
    layout="wide"
)

# Initialize session state
if 'step' not in st.session_state:
    st.session_state.step = 1
if 'processed_data' not in st.session_state:
    st.session_state.processed_data = None
if 'naming_scheme' not in st.session_state:
    st.session_state.naming_scheme = []
if 'separators' not in st.session_state:
    st.session_state.separators = {}
if 'custom_prefix' not in st.session_state:
    st.session_state.custom_prefix = 'SP'
if 'errors' not in st.session_state:
    st.session_state.errors = []
if 'current_page' not in st.session_state:
    st.session_state.current_page = 1
if 'sp_sheet_data' not in st.session_state:
    st.session_state.sp_sheet_data = None
if 'global_asin_performance' not in st.session_state:
    st.session_state.global_asin_performance = {}
if 'preview_options' not in st.session_state:
    st.session_state.preview_options = {
        'targetingType': 'M',
        'matchTypes': ['Ex', 'Br'],
        'biddingStrategy': 'Fix',
        'bestPlacement': 'TOS',
        'adGroupCount': 3
    }
if 'unique_asins' not in st.session_state:
    st.session_state.unique_asins = []
if 'asin_short_names' not in st.session_state:
    st.session_state.asin_short_names = {}
if 'use_short_names' not in st.session_state:
    st.session_state.use_short_names = False

# Helper Functions
def extract_unique_asins(campaigns):
    """Extract all unique advertised ASINs from campaigns"""
    unique_asins = set()
    for campaign in campaigns.values():
        unique_asins.update(campaign['all_asins'])
    return sorted(list(unique_asins))

def create_asin_template(unique_asins):
    """Create ASIN short names template file"""
    template_df = pd.DataFrame({
        'ASINs': unique_asins,
        'Short_Name': [''] * len(unique_asins)
    })

    # Convert to Excel with data validation
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        template_df.to_excel(writer, index=False, sheet_name='ASIN_Short_Names')

        # Get the worksheet to add data validation
        worksheet = writer.sheets['ASIN_Short_Names']
        from openpyxl.worksheet.datavalidation import DataValidation

        # Add data validation for Short_Name column (max 50 characters)
        dv = DataValidation(type="textLength", operator="lessThanOrEqual", formula1="50",
                           allow_blank=True, showErrorMessage=True,
                           errorTitle="Invalid Short Name",
                           error="Short name cannot exceed 50 characters")

        # Apply validation to column B (Short_Name) for all rows
        worksheet.add_data_validation(dv)
        dv.add(f'B2:B{len(unique_asins) + 1}')

    output.seek(0)
    return output

def validate_asin_shortname_file(uploaded_df, expected_asins):
    """Validate the uploaded ASIN short names file"""
    errors = []

    # Check headers
    if list(uploaded_df.columns) != ['ASINs', 'Short_Name']:
        errors.append("Invalid headers. Expected: 'ASINs' and 'Short_Name'")
        return False, errors, {}

    # Check for missing ASINs column data
    if uploaded_df['ASINs'].isnull().any():
        errors.append("ASINs column contains empty values")

    # Check for duplicate ASINs
    if uploaded_df['ASINs'].duplicated().any():
        errors.append("ASINs column contains duplicate values")

    # Check if all ASINs match expected ASINs (irrespective of sorting)
    uploaded_asins = set(uploaded_df['ASINs'].dropna().astype(str).tolist())
    expected_asins_set = set(expected_asins)

    if uploaded_asins != expected_asins_set:
        missing_in_upload = expected_asins_set - uploaded_asins
        extra_in_upload = uploaded_asins - expected_asins_set

        if missing_in_upload:
            errors.append(f"Missing ASINs in uploaded file: {', '.join(list(missing_in_upload)[:5])}{'...' if len(missing_in_upload) > 5 else ''}")
        if extra_in_upload:
            errors.append(f"Unexpected ASINs in uploaded file: {', '.join(list(extra_in_upload)[:5])}{'...' if len(extra_in_upload) > 5 else ''}")

    # Check Short_Name length (max 50 characters)
    short_names = uploaded_df['Short_Name'].dropna().astype(str)
    invalid_lengths = short_names[short_names.str.len() > 50]

    if not invalid_lengths.empty:
        errors.append(f"Found {len(invalid_lengths)} short name(s) exceeding 50 characters")

    # If there are errors, return early
    if errors:
        return False, errors, {}

    # Create mapping dictionary
    asin_shortname_map = {}
    for _, row in uploaded_df.iterrows():
        asin = str(row['ASINs'])
        short_name = str(row['Short_Name']).strip() if pd.notna(row['Short_Name']) else ''
        if short_name:  # Only add if short name is not empty
            asin_shortname_map[asin] = short_name

    return True, [], asin_shortname_map

def find_sp_sheet(uploaded_file):
    """Find the Sponsored Products sheet in the Excel file and clean it"""
    # Read the Excel file into a pandas ExcelFile object
    excel_file = pd.ExcelFile(uploaded_file)
    sheet_names = excel_file.sheet_names
    
    sp_sheet_name = None
    sp_df = None
    
    # First, try to find by sheet name
    for sheet_name in sheet_names:
        if 'Sponsored Products' in sheet_name:
            sp_df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            sp_sheet_name = sheet_name
            break
    
    # Fallback: check if column A contains "Sponsored Products"
    if sp_df is None:
        for sheet_name in sheet_names:
            df = pd.read_excel(excel_file, sheet_name=sheet_name, header=None)
            column_a = df.iloc[:, 0].dropna()
            
            if len(column_a) > 0 and any('Sponsored Products' in str(val) for val in column_a):
                sp_df = df
                sp_sheet_name = sheet_name
                break
    
    if sp_df is None:
        return None, None
    
    # Clean the dataframe: Remove Negative keyword and Campaign Negative Keyword rows
    # Column B (index 1) contains the Entity type
    entities_to_remove = ['Negative keyword', 'Campaign Negative Keyword']
    sp_df = sp_df[~sp_df.iloc[:, 1].isin(entities_to_remove)]
    
    # Reset index after filtering
    sp_df = sp_df.reset_index(drop=True)
    
    return sp_sheet_name, sp_df

def determine_match_code(match_type):
    """Determine match type code"""
    if pd.isna(match_type):
        return None
    match_type = str(match_type).lower()
    if 'exact' in match_type:
        return 'Ex'
    elif 'phrase' in match_type:
        return 'Ph'
    elif 'broad' in match_type:
        return 'Br'
    return None

def determine_product_code(expression):
    """Determine product targeting code"""
    if pd.isna(expression):
        return None
    expression = str(expression).lower()
    if 'asin=' in expression:
        return 'PAT'
    elif 'category=' in expression:
        return 'CAT'
    return None

def determine_placement_code(placement):
    """Determine placement code"""
    if pd.isna(placement):
        return None
    placement = str(placement)
    if 'Top' in placement:
        return 'TOS'
    elif 'Product Page' in placement:
        return 'PP'
    elif 'Rest Of Search' in placement:
        return 'ROS'
    return None

def safe_float(value):
    """Safely convert value to float"""
    try:
        return float(value) if pd.notna(value) else 0.0
    except:
        return 0.0

def process_sponsored_products_sheet(df):
    """Process the Sponsored Products sheet and extract campaign data"""
    campaigns = {}
    global_asin_performance = defaultdict(lambda: {
        'orders_sum': 0, 'clicks_sum': 0, 'sales_sum': 0, 
        'spend_sum': 0, 'impressions': 0, 'orders': 0, 
        'conversion_rate': 0, 'roas': 0
    })
    errors = []
    
    # Phase 1: Data Collection
    for idx, row in df.iterrows():
        if idx == 0:  # Skip header
            continue
        
        if pd.isna(row.iloc[1]) or pd.isna(row.iloc[3]):
            continue
        
        entity = str(row.iloc[1])
        campaign_id = str(row.iloc[3])
        ad_group_id = str(row.iloc[4]) if pd.notna(row.iloc[4]) else None
        
        # Initialize campaign
        if campaign_id not in campaigns:
            campaigns[campaign_id] = {
                'id': campaign_id,
                'name': '',
                'targeting_type': '',
                'bidding_strategy': '',
                'ad_groups': {},
                'placements': {},
                'match_types': set(),
                'all_asins': [],
                'best_asin': None,
                'best_match_type': None,
                'best_placement': 'N/A'
            }
        
        campaign = campaigns[campaign_id]
        
        # Process Campaign Entity
        if entity == 'Campaign':
            campaign['name'] = str(row.iloc[9]) if pd.notna(row.iloc[9]) else ''
            targeting = str(row.iloc[16]) if pd.notna(row.iloc[16]) else ''
            campaign['targeting_type'] = 'A' if 'auto' in targeting.lower() else 'M'
            
            bidding = str(row.iloc[32]) if pd.notna(row.iloc[32]) else ''
            if 'Fixed' in bidding:
                campaign['bidding_strategy'] = 'Fix'
            elif 'down only' in bidding:
                campaign['bidding_strategy'] = 'DwnO'
            elif 'up and down' in bidding:
                campaign['bidding_strategy'] = 'UnD'
        
        # Process Ad Group Entity
        if entity == 'Ad Group' and ad_group_id:
            if ad_group_id not in campaign['ad_groups']:
                campaign['ad_groups'][ad_group_id] = {
                    'id': ad_group_id,
                    'name': str(row.iloc[10]) if pd.notna(row.iloc[10]) else '',
                    'match_types': {},
                    'asins': [],
                    'best_asin': None,
                    'best_match_type': None
                }
        
        # Process Product Ad Entity
        if entity == 'Product Ad' and ad_group_id:
            asin = str(row.iloc[22]) if pd.notna(row.iloc[22]) else None
            if asin and ad_group_id in campaign['ad_groups']:
                asin_data = {
                    'sku': str(row.iloc[21]) if pd.notna(row.iloc[21]) else '',
                    'asin': asin,
                    'orders': safe_float(row.iloc[41]),
                    'conversion_rate': safe_float(row.iloc[44]),
                    'roas': safe_float(row.iloc[47]),
                    'clicks': safe_float(row.iloc[39]),
                    'impressions': safe_float(row.iloc[38])
                }
                campaign['ad_groups'][ad_group_id]['asins'].append(asin_data)
                campaign['all_asins'].append(asin)
                
                # Track global ASIN performance
                global_asin_performance[asin]['orders_sum'] += asin_data['orders']
                global_asin_performance[asin]['clicks_sum'] += asin_data['clicks']
                global_asin_performance[asin]['sales_sum'] += safe_float(row.iloc[42])
                global_asin_performance[asin]['spend_sum'] += safe_float(row.iloc[40])
                global_asin_performance[asin]['impressions'] += asin_data['impressions']
        
        # Process Keyword Entity
        if entity == 'Keyword' and ad_group_id and ad_group_id in campaign['ad_groups']:
            match_type = row.iloc[31]
            match_code = determine_match_code(match_type)
            
            if match_code:
                if match_code not in campaign['ad_groups'][ad_group_id]['match_types']:
                    campaign['ad_groups'][ad_group_id]['match_types'][match_code] = {
                        'orders': 0, 'clicks': 0, 'sales': 0, 'spend': 0
                    }
                
                campaign['ad_groups'][ad_group_id]['match_types'][match_code]['orders'] += safe_float(row.iloc[41])
                campaign['ad_groups'][ad_group_id]['match_types'][match_code]['clicks'] += safe_float(row.iloc[39])
                campaign['ad_groups'][ad_group_id]['match_types'][match_code]['sales'] += safe_float(row.iloc[42])
                campaign['ad_groups'][ad_group_id]['match_types'][match_code]['spend'] += safe_float(row.iloc[40])
                campaign['match_types'].add(match_code)
        
        # Process Product Targeting Entity
        if entity == 'Product Targeting' and ad_group_id and ad_group_id in campaign['ad_groups']:
            expression = row.iloc[35]
            match_code = determine_product_code(expression)
            
            if match_code:
                if match_code not in campaign['ad_groups'][ad_group_id]['match_types']:
                    campaign['ad_groups'][ad_group_id]['match_types'][match_code] = {
                        'orders': 0, 'clicks': 0, 'sales': 0, 'spend': 0
                    }
                
                campaign['ad_groups'][ad_group_id]['match_types'][match_code]['orders'] += safe_float(row.iloc[41])
                campaign['ad_groups'][ad_group_id]['match_types'][match_code]['clicks'] += safe_float(row.iloc[39])
                campaign['ad_groups'][ad_group_id]['match_types'][match_code]['sales'] += safe_float(row.iloc[42])
                campaign['ad_groups'][ad_group_id]['match_types'][match_code]['spend'] += safe_float(row.iloc[40])
                campaign['match_types'].add(match_code)
        
        # Process Bidding Adjustment Entity (Placements)
        if entity == 'Bidding Adjustment':
            placement = row.iloc[33]
            placement_code = determine_placement_code(placement)
            
            if placement_code:
                if placement_code not in campaign['placements']:
                    campaign['placements'][placement_code] = {
                        'orders': 0, 'clicks': 0, 'sales': 0, 'spend': 0, 'impressions': 0
                    }
                
                campaign['placements'][placement_code]['orders'] += safe_float(row.iloc[41])
                campaign['placements'][placement_code]['clicks'] += safe_float(row.iloc[39])
                campaign['placements'][placement_code]['sales'] += safe_float(row.iloc[42])
                campaign['placements'][placement_code]['spend'] += safe_float(row.iloc[40])
                campaign['placements'][placement_code]['impressions'] += safe_float(row.iloc[38])
    
    # Phase 2: Calculate global ASIN metrics
    for asin, perf in global_asin_performance.items():
        perf['orders'] = perf['orders_sum']
        perf['conversion_rate'] = perf['orders_sum'] / perf['clicks_sum'] if perf['clicks_sum'] > 0 else 0
        perf['roas'] = perf['sales_sum'] / perf['spend_sum'] if perf['spend_sum'] > 0 else 0
    
    # Phase 3: Analyze campaigns
    campaigns_to_delete = []
    
    for campaign_id, campaign in campaigns.items():
        # Collect all ASINs
        all_campaign_asins = []
        for ad_group in campaign['ad_groups'].values():
            all_campaign_asins.extend(ad_group['asins'])
        
        # Validate campaign
        if len(all_campaign_asins) == 0:
            errors.append(f"Campaign {campaign_id}: No Product Ads found")
            campaigns_to_delete.append(campaign_id)
            continue
        
        # Find best ASIN at campaign level
        all_campaign_asins.sort(key=lambda x: (-x['orders'], -x['conversion_rate'], -x['roas']))
        best_campaign_asin = all_campaign_asins[0]
        
        if best_campaign_asin['orders'] == 0 and best_campaign_asin['clicks'] == 0:
            all_campaign_asins.sort(key=lambda x: (-x['clicks'], -x['impressions']))
            best_campaign_asin = all_campaign_asins[0]
            
            if best_campaign_asin['clicks'] == 0:
                campaign_asins_global = [(asin, global_asin_performance[asin]['orders']) 
                                        for asin in campaign['all_asins']]
                campaign_asins_global.sort(key=lambda x: -x[1])
                if campaign_asins_global:
                    best_campaign_asin = {'asin': campaign_asins_global[0][0]}
        
        campaign['best_asin'] = best_campaign_asin.get('asin', 'N/A')
        
        # Find best match type at campaign level
        campaign_match_type_perf = defaultdict(lambda: {'orders': 0, 'clicks': 0, 'sales': 0, 'spend': 0})
        
        for ad_group in campaign['ad_groups'].values():
            for match_type, perf in ad_group['match_types'].items():
                campaign_match_type_perf[match_type]['orders'] += perf['orders']
                campaign_match_type_perf[match_type]['clicks'] += perf['clicks']
                campaign_match_type_perf[match_type]['sales'] += perf['sales']
                campaign_match_type_perf[match_type]['spend'] += perf['spend']
        
        match_type_list = []
        for match_type, perf in campaign_match_type_perf.items():
            conv_rate = perf['orders'] / perf['clicks'] if perf['clicks'] > 0 else 0
            roas = perf['sales'] / perf['spend'] if perf['spend'] > 0 else 0
            match_type_list.append({
                'type': match_type,
                'orders': perf['orders'],
                'conversion_rate': conv_rate,
                'roas': roas
            })
        
        match_type_list.sort(key=lambda x: (-x['orders'], -x['conversion_rate'], -x['roas']))
        campaign['best_match_type'] = match_type_list[0]['type'] if match_type_list else None
        
        # Find best placement
        placement_list = []
        for placement, perf in campaign['placements'].items():
            conv_rate = perf['orders'] / perf['clicks'] if perf['clicks'] > 0 else 0
            roas = perf['sales'] / perf['spend'] if perf['spend'] > 0 else 0
            placement_list.append({
                'placement': placement,
                'orders': perf['orders'],
                'roas': roas,
                'conversion_rate': conv_rate,
                'clicks': perf['clicks'],
                'impressions': perf['impressions']
            })
        
        placement_list.sort(key=lambda x: (-x['orders'], -x['roas'], -x['conversion_rate']))
        
        if placement_list and placement_list[0]['orders'] == 0:
            placement_list.sort(key=lambda x: (-x['clicks'], -x['impressions']))
        
        campaign['best_placement'] = placement_list[0]['placement'] if placement_list else 'N/A'
        
        # Process each ad group
        for ad_group_id, ad_group in campaign['ad_groups'].items():
            if ad_group['asins']:
                ad_group['asins'].sort(key=lambda x: (-x['orders'], -x['conversion_rate'], -x['roas']))
                best_ag_asin = ad_group['asins'][0]
                
                if best_ag_asin['orders'] == 0:
                    ad_group['asins'].sort(key=lambda x: (-x['clicks'], -x['impressions']))
                    best_ag_asin = ad_group['asins'][0]
                    
                    if best_ag_asin['clicks'] == 0:
                        ag_asins_global = [(asin_obj['asin'], global_asin_performance[asin_obj['asin']]['orders']) 
                                          for asin_obj in ad_group['asins']]
                        ag_asins_global.sort(key=lambda x: -x[1])
                        if ag_asins_global:
                            best_ag_asin = {'asin': ag_asins_global[0][0]}
                
                ad_group['best_asin'] = best_ag_asin.get('asin', 'N/A')
            
            # Find best match type for ad group
            ag_match_type_list = []
            for match_type, perf in ad_group['match_types'].items():
                conv_rate = perf['orders'] / perf['clicks'] if perf['clicks'] > 0 else 0
                roas = perf['sales'] / perf['spend'] if perf['spend'] > 0 else 0
                ag_match_type_list.append({
                    'type': match_type,
                    'orders': perf['orders'],
                    'conversion_rate': conv_rate,
                    'roas': roas
                })
            
            ag_match_type_list.sort(key=lambda x: (-x['orders'], -x['conversion_rate'], -x['roas']))
            ad_group['best_match_type'] = ag_match_type_list[0]['type'] if ag_match_type_list else None
    
    # Remove invalid campaigns
    for campaign_id in campaigns_to_delete:
        del campaigns[campaign_id]
    
    return campaigns, global_asin_performance, errors

def generate_preview_name(naming_scheme, separators, custom_prefix, preview_options):
    """Generate preview name using preview options for visualization"""
    name_parts = []

    for idx, element in enumerate(naming_scheme):
        part = ''

        if element == 'prefix':
            part = custom_prefix
        elif element == 'targetingType':
            part = preview_options.get('targetingType', 'M')
        elif element == 'matchTypes':
            if preview_options.get('targetingType', 'M') == 'A':
                part = 'Auto'
            else:
                match_types = preview_options.get('matchTypes', ['Ex', 'Br'])
                part = f"[{','.join(match_types)}]"
        elif element == 'adGroupCount':
            count = preview_options.get('adGroupCount', 1)
            part = f"{count}AdG"
        elif element == 'bestAsin':
            part = 'B0XXXXXXXX'
        elif element == 'biddingStrategy':
            part = preview_options.get('biddingStrategy', 'Fix')
        elif element == 'bestPlacement':
            part = preview_options.get('bestPlacement', 'TOS')

        name_parts.append(part)

        if idx < len(naming_scheme) - 1:
            name_parts.append(separators.get(idx, '-'))

    return ''.join(name_parts)

def apply_asin_shortname(asin, asin_shortname_map):
    """Apply short name mapping to ASIN"""
    if asin in asin_shortname_map:
        short_name = asin_shortname_map[asin]
        return f"{asin}-{short_name}"
    return asin

def deduplicate_names(names_list):
    """
    Deduplicate names by adding sequential numbers (1, 2, 3, etc.) to duplicates.
    Returns a list of deduplicated names in the same order.

    Args:
        names_list: List of (identifier, name) tuples

    Returns:
        Dictionary mapping identifier to deduplicated name
    """
    name_counts = {}
    name_usage = {}
    deduplicated = {}

    # First pass: count occurrences of each name
    for identifier, name in names_list:
        name_counts[name] = name_counts.get(name, 0) + 1

    # Second pass: assign deduplicated names
    for identifier, name in names_list:
        if name_counts[name] > 1:
            # This name appears multiple times, add a number
            if name not in name_usage:
                name_usage[name] = 1
            else:
                name_usage[name] += 1

            deduplicated[identifier] = f"{name}-{name_usage[name]}"
        else:
            # Unique name, no numbering needed
            deduplicated[identifier] = name

    return deduplicated

def generate_campaign_name(campaign, naming_scheme, separators, custom_prefix, asin_shortname_map=None, use_short_names=False):
    """Generate campaign name based on naming scheme"""
    name_parts = []

    for idx, element in enumerate(naming_scheme):
        part = ''

        if element == 'prefix':
            part = custom_prefix
        elif element == 'targetingType':
            part = campaign['targeting_type']
        elif element == 'matchTypes':
            if campaign['targeting_type'] == 'A':
                part = 'Auto'
            else:
                match_types = sorted(list(campaign['match_types']))
                highlighted = []
                for mt in match_types:
                    if mt == campaign['best_match_type']:
                        highlighted.append(f"*{mt}*")
                    else:
                        highlighted.append(mt)
                part = f"[{','.join(highlighted)}]"
        elif element == 'adGroupCount':
            part = f"{len(campaign['ad_groups'])}AdG"
        elif element == 'bestAsin':
            asin = campaign['best_asin'] or 'N/A'
            if use_short_names and asin_shortname_map:
                part = apply_asin_shortname(asin, asin_shortname_map)
            else:
                part = asin
        elif element == 'biddingStrategy':
            part = campaign['bidding_strategy']
        elif element == 'bestPlacement':
            part = campaign['best_placement']

        name_parts.append(part)

        if idx < len(naming_scheme) - 1:
            name_parts.append(separators.get(idx, '-'))

    return ''.join(name_parts)

def generate_adgroup_name(ad_group, asin_shortname_map=None, use_short_names=False):
    """Generate ad group name"""
    best_asin = ad_group.get('best_asin') or 'N/A'
    best_match = ad_group.get('best_match_type') or 'N/A'

    if use_short_names and asin_shortname_map:
        best_asin = apply_asin_shortname(best_asin, asin_shortname_map)

    return f"{best_asin}-{best_match}"

def generate_nomenclature_document(naming_scheme, separators, custom_prefix, campaigns):
    """Generate a comprehensive nomenclature document explaining the naming scheme"""

    # Build the format string
    format_parts = []
    for idx, element in enumerate(naming_scheme):
        if element == 'prefix':
            format_parts.append(f"[{custom_prefix}]")
        elif element == 'targetingType':
            format_parts.append("[A/M]")
        elif element == 'matchTypes':
            format_parts.append("[MatchTypes]")
        elif element == 'adGroupCount':
            format_parts.append("[#AdG]")
        elif element == 'bestAsin':
            format_parts.append("[BestASIN]")
        elif element == 'biddingStrategy':
            format_parts.append("[Strategy]")
        elif element == 'bestPlacement':
            format_parts.append("[Placement]")

        if idx < len(naming_scheme) - 1:
            format_parts.append(separators.get(idx, '-'))

    format_string = ''.join(format_parts)

    # Generate example campaigns
    example_campaigns = []
    if campaigns:
        campaign_list = list(campaigns.values())[:3]  # Get up to 3 examples
        for camp in campaign_list:
            old_name = camp['name']
            new_name = generate_campaign_name(camp, naming_scheme, separators, custom_prefix)
            example_campaigns.append({
                'old': old_name,
                'new': new_name,
                'targeting': 'Auto' if camp['targeting_type'] == 'A' else 'Manual',
                'ad_groups': len(camp['ad_groups'])
            })

    # Create the document content
    doc = f"""# AMAZON ADS CAMPAIGN NOMENCLATURE GUIDE
Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}

================================================================================
CAMPAIGN NAMING SCHEME
================================================================================

Your Custom Format:
{format_string}

--------------------------------------------------------------------------------
NAMING ELEMENTS EXPLANATION
--------------------------------------------------------------------------------

"""

    # Add explanation for each element
    for idx, element in enumerate(naming_scheme):
        doc += f"{idx + 1}. "

        if element == 'prefix':
            doc += f"PREFIX: '{custom_prefix}'\n"
            doc += f"   - A fixed identifier for all campaigns\n"
            doc += f"   - Helps you quickly identify campaigns in Amazon Ads console\n"

        elif element == 'targetingType':
            doc += "TARGETING TYPE\n"
            doc += "   - A = Auto Targeting (Amazon automatically targets keywords)\n"
            doc += "   - M = Manual Targeting (You select specific keywords or products)\n"

        elif element == 'matchTypes':
            doc += "MATCH TYPES\n"
            doc += "   - Shows all match types used in the campaign\n"
            doc += "   - Auto: Campaign uses automatic targeting\n"
            doc += "   - Manual campaigns show:\n"
            doc += "     • Ex = Exact Match\n"
            doc += "     • Ph = Phrase Match\n"
            doc += "     • Br = Broad Match\n"
            doc += "     • PAT = Product Attribute Targeting\n"
            doc += "     • CAT = Category Targeting\n"
            doc += "   - Best performing match type is marked with asterisks (*)\n"
            doc += "   - Example: [Ex,*Br*,Ph] means Broad is performing best\n"

        elif element == 'adGroupCount':
            doc += "AD GROUP COUNT\n"
            doc += "   - Shows the number of ad groups in this campaign\n"
            doc += "   - Format: #AdG (e.g., 3AdG = 3 ad groups)\n"
            doc += "   - Helps you understand campaign structure at a glance\n"

        elif element == 'bestAsin':
            doc += "BEST ASIN\n"
            doc += "   - The best performing product (ASIN) in this campaign\n"
            doc += "   - Determined by: Orders > Conversion Rate > ROAS\n"
            doc += "   - If no orders: Uses Clicks > Impressions\n"
            doc += "   - If no campaign data: Uses global ASIN performance\n"

        elif element == 'biddingStrategy':
            doc += "BIDDING STRATEGY\n"
            doc += "   - Fix = Fixed Bids (legacy)\n"
            doc += "   - DwnO = Dynamic Bids - Down Only\n"
            doc += "   - UnD = Dynamic Bids - Up and Down\n"

        elif element == 'bestPlacement':
            doc += "BEST PLACEMENT\n"
            doc += "   - Shows which ad placement is performing best\n"
            doc += "   - TOS = Top of Search (first page)\n"
            doc += "   - PP = Product Pages\n"
            doc += "   - ROS = Rest of Search\n"
            doc += "   - Determined by: Orders > ROAS > Conversion Rate\n"

        if idx < len(naming_scheme) - 1:
            separator = separators.get(idx, '-')
            doc += f"\n   Separator: '{separator}'\n"

        doc += "\n"

    doc += """
================================================================================
AD GROUP NAMING SCHEME
================================================================================

Format: [BestASIN]-[BestMatchType]

Components:
1. Best ASIN: The top performing product in the ad group
2. Best Match Type: The best performing match type in the ad group
   - Uses same logic as campaign level (Orders > Conv Rate > ROAS)

Example: B07XYZ1234-Ex
   - B07XYZ1234 is the best performing ASIN
   - Ex means Exact match is performing best

"""

    # Add examples if available
    if example_campaigns:
        doc += """================================================================================
EXAMPLE CAMPAIGNS FROM YOUR DATA
================================================================================

"""
        for i, ex in enumerate(example_campaigns, 1):
            doc += f"Example {i}:\n"
            doc += f"  OLD NAME: {ex['old']}\n"
            doc += f"  NEW NAME: {ex['new']}\n"
            doc += f"  Targeting: {ex['targeting']}\n"
            doc += f"  Ad Groups: {ex['ad_groups']}\n\n"

    doc += """================================================================================
PERFORMANCE RANKING LOGIC
================================================================================

How "Best" Elements are Determined:

1. BEST ASIN (Campaign & Ad Group Level):
   - Primary: Highest Orders
   - Secondary: Highest Conversion Rate
   - Tertiary: Highest ROAS
   - Fallback (no orders): Highest Clicks > Impressions
   - Final Fallback: Global ASIN performance across all campaigns

2. BEST MATCH TYPE (Campaign & Ad Group Level):
   - Primary: Highest Orders
   - Secondary: Highest Conversion Rate
   - Tertiary: Highest ROAS

3. BEST PLACEMENT (Campaign Level):
   - Primary: Highest Orders
   - Secondary: Highest ROAS
   - Tertiary: Highest Conversion Rate
   - Fallback (no orders): Highest Clicks > Impressions

================================================================================
IMPORTANT NOTES
================================================================================

• Each campaign name is unique and data-driven
• Names reflect actual campaign performance and structure
• The naming scheme is a FORMAT - each campaign uses its own data
• Asterisks (*) in match types indicate the best performer
• All metrics are calculated from your uploaded bulk report data
• Campaign names update based on current performance when regenerated

================================================================================
GLOSSARY
================================================================================

ASIN: Amazon Standard Identification Number (unique product identifier)
ROAS: Return on Ad Spend (Revenue ÷ Spend)
Conversion Rate: Orders ÷ Clicks
Orders: Number of purchases attributed to the ad
Clicks: Number of times the ad was clicked
Impressions: Number of times the ad was displayed

================================================================================
SUPPORT
================================================================================

For questions or issues with the renaming tool:
- Review your naming scheme in Step 2
- Check the preview to understand the format
- Verify your bulk report contains complete data
- Use the error log if any warnings were generated

Generated by Amazon Ads Campaign Renamer Tool
https://github.com/anthropics/claude-code
================================================================================
"""

    return doc

def create_bulk_file(campaigns, naming_scheme, separators, custom_prefix, asin_shortname_map=None, use_short_names=False):
    """Create bulk update file with deduplication"""
    output_data = []

    # Header row
    output_data.append([
        'Product', 'Entity', 'Operation', 'Campaign ID', 'Ad Group ID',
        '', '', '', '', 'Campaign Name', 'Ad Group Name'
    ])

    # Step 1: Generate all campaign names
    campaign_names_list = []
    for campaign in campaigns.values():
        new_campaign_name = generate_campaign_name(
            campaign, naming_scheme, separators, custom_prefix,
            asin_shortname_map, use_short_names
        )
        campaign_names_list.append((campaign['id'], new_campaign_name))

    # Step 2: Deduplicate campaign names
    deduplicated_campaign_names = deduplicate_names(campaign_names_list)

    # Step 3: Process each campaign
    for campaign in campaigns.values():
        campaign_id = campaign['id']
        final_campaign_name = deduplicated_campaign_names[campaign_id]

        # Add campaign row
        output_data.append([
            'Sponsored Products', 'Campaign', 'update', campaign_id, '',
            '', '', '', '', final_campaign_name, ''
        ])

        # Step 3a: Generate all ad group names for this campaign
        adgroup_names_list = []
        for ad_group in campaign['ad_groups'].values():
            new_adgroup_name = generate_adgroup_name(ad_group, asin_shortname_map, use_short_names)
            adgroup_names_list.append((ad_group['id'], new_adgroup_name))

        # Step 3b: Deduplicate ad group names within this campaign
        deduplicated_adgroup_names = deduplicate_names(adgroup_names_list)

        # Step 3c: Add ad group rows
        for ad_group in campaign['ad_groups'].values():
            final_adgroup_name = deduplicated_adgroup_names[ad_group['id']]
            output_data.append([
                'Sponsored Products', 'Ad Group', 'update', campaign_id, ad_group['id'],
                '', '', '', '', '', final_adgroup_name
            ])

    return pd.DataFrame(output_data)

# Main App
st.title("📊 Amazon Ads Campaign Renaming Tool")

# Progress indicator
progress_cols = st.columns(4)
for i, col in enumerate(progress_cols):
    with col:
        if i + 1 < st.session_state.step:
            st.success(f"✓ Step {i+1}")
        elif i + 1 == st.session_state.step:
            st.info(f"→ Step {i+1}")
        else:
            st.text(f"  Step {i+1}")

st.divider()

# STEP 1: File Upload
if st.session_state.step == 1:
    st.header("Step 1: Upload Your File")
    st.write("Upload your Amazon Ads bulk report (.xlsx format)")
    
    uploaded_file = st.file_uploader("Choose an Excel file", type=['xlsx'])
    
    if uploaded_file:
        try:
            with st.spinner("Processing file..."):
                sheet_name, df = find_sp_sheet(uploaded_file)
                
                if sheet_name:
                    st.success(f"✓ Found Sponsored Products sheet: {sheet_name}")
                    
                    campaigns, global_asin_perf, errors = process_sponsored_products_sheet(df)

                    st.session_state.processed_data = campaigns
                    st.session_state.global_asin_performance = global_asin_perf
                    st.session_state.errors = errors
                    st.session_state.sp_sheet_data = df

                    # Extract unique ASINs for template
                    st.session_state.unique_asins = extract_unique_asins(campaigns)
                    
                    st.info(f"Processed {len(campaigns)} campaigns")
                    
                    if st.button("Continue to Naming Scheme →", type="primary"):
                        st.session_state.step = 2
                        st.rerun()
                else:
                    st.error("❌ No Sponsored Products sheet found in the file")
        except Exception as e:
            st.error(f"Error processing file: {str(e)}")

# STEP 2: Naming Scheme Builder
elif st.session_state.step == 2:
    st.header("Step 2: Build Your Naming Scheme")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Available Elements")
        
        if st.button("➕ Prefix", use_container_width=True):
            if 'prefix' not in st.session_state.naming_scheme:
                st.session_state.naming_scheme.append('prefix')
                st.rerun()
        
        st.session_state.custom_prefix = st.text_input("Prefix Text:", value=st.session_state.custom_prefix)
        
        if st.button("➕ Targeting Type (A/M)", use_container_width=True):
            if 'targetingType' not in st.session_state.naming_scheme:
                st.session_state.naming_scheme.append('targetingType')
                st.rerun()
        
        if st.button("➕ Match Types [Ex,Br,PAT]", use_container_width=True):
            if 'matchTypes' not in st.session_state.naming_scheme:
                st.session_state.naming_scheme.append('matchTypes')
                st.rerun()
        
        if st.button("➕ Ad Group Count (3AdG)", use_container_width=True):
            if 'adGroupCount' not in st.session_state.naming_scheme:
                st.session_state.naming_scheme.append('adGroupCount')
                st.rerun()
        
        if st.button("➕ Best ASIN", use_container_width=True):
            if 'bestAsin' not in st.session_state.naming_scheme:
                st.session_state.naming_scheme.append('bestAsin')
                st.rerun()
        
        if st.button("➕ Bidding Strategy", use_container_width=True):
            if 'biddingStrategy' not in st.session_state.naming_scheme:
                st.session_state.naming_scheme.append('biddingStrategy')
                st.rerun()

        if st.button("➕ Best Placement", use_container_width=True):
            if 'bestPlacement' not in st.session_state.naming_scheme:
                st.session_state.naming_scheme.append('bestPlacement')
                st.rerun()
    
    with col2:
        st.subheader("Your Naming Scheme")

        # Create placeholder for preview (will be filled after widgets are rendered)
        preview_placeholder = st.empty()
        preview_caption_placeholder = st.empty()
        preview_divider_placeholder = st.empty()

        if not st.session_state.naming_scheme:
            st.info("Add elements from the left to build your naming scheme")
        else:
            for idx, element in enumerate(st.session_state.naming_scheme):
                with st.container():
                    # Create a row for the element
                    elem_row = st.columns([4, 2, 1])
                    
                    # Element name and preview selector
                    with elem_row[0]:
                        element_display_name = {
                            'prefix': 'Prefix',
                            'targetingType': 'Targeting Type',
                            'matchTypes': 'Match Types',
                            'adGroupCount': 'Ad Group Count',
                            'bestAsin': 'Best ASIN',
                            'biddingStrategy': 'Bidding Strategy',
                            'bestPlacement': 'Best Placement'
                        }

                        # Show element name with expander for configurable preview options
                        if element in ['targetingType', 'matchTypes', 'biddingStrategy', 'bestPlacement', 'adGroupCount']:
                            with st.expander(f"**{idx + 1}. {element_display_name.get(element, element)}**", expanded=False):
                                st.caption("_Preview settings (for visualization only):_")

                                if element == 'targetingType':
                                    st.session_state.preview_options['targetingType'] = st.selectbox(
                                        "Preview as:",
                                        options=['A', 'M'],
                                        index=0 if st.session_state.preview_options.get('targetingType', 'M') == 'A' else 1,
                                        key=f"prev_targeting_{idx}"
                                    )

                                elif element == 'matchTypes':
                                    # Disable if targeting type is Auto
                                    is_auto = st.session_state.preview_options.get('targetingType', 'M') == 'A'
                                    if is_auto:
                                        st.info("Match Types are set to 'Auto' when Targeting Type is Auto")
                                    else:
                                        st.session_state.preview_options['matchTypes'] = st.multiselect(
                                            "Preview match types:",
                                            options=['Ex', 'Ph', 'Br', 'PAT', 'CAT'],
                                            default=st.session_state.preview_options.get('matchTypes', ['Ex', 'Br']),
                                            key=f"prev_match_{idx}"
                                        )

                                elif element == 'biddingStrategy':
                                    st.session_state.preview_options['biddingStrategy'] = st.selectbox(
                                        "Preview as:",
                                        options=['Fix', 'UnD', 'DwnO'],
                                        index=['Fix', 'UnD', 'DwnO'].index(st.session_state.preview_options.get('biddingStrategy', 'Fix')),
                                        key=f"prev_bidding_{idx}"
                                    )

                                elif element == 'bestPlacement':
                                    st.session_state.preview_options['bestPlacement'] = st.selectbox(
                                        "Preview as:",
                                        options=['TOS', 'PP', 'ROS'],
                                        index=['TOS', 'PP', 'ROS'].index(st.session_state.preview_options.get('bestPlacement', 'TOS')),
                                        key=f"prev_placement_{idx}"
                                    )

                                elif element == 'adGroupCount':
                                    st.session_state.preview_options['adGroupCount'] = st.number_input(
                                        "Preview count:",
                                        min_value=1,
                                        max_value=999,
                                        value=st.session_state.preview_options.get('adGroupCount', 3),
                                        step=1,
                                        key=f"prev_adgcount_{idx}"
                                    )
                        else:
                            # For non-configurable elements
                            st.write(f"**{idx + 1}. {element_display_name.get(element, element)}**")
                    
                    # Separator input
                    with elem_row[1]:
                        if idx < len(st.session_state.naming_scheme) - 1:
                            sep = st.text_input(
                                "Separator:",
                                value=st.session_state.separators.get(idx, '-'),
                                key=f"sep_{idx}",
                                max_chars=3
                            )
                            st.session_state.separators[idx] = sep
                    
                    # Delete button
                    with elem_row[2]:
                        if st.button("🗑️", key=f"del_{idx}"):
                            st.session_state.naming_scheme.pop(idx)
                            if idx in st.session_state.separators:
                                del st.session_state.separators[idx]
                            st.rerun()

            # Now render the preview at the top using the placeholders
            preview_name = generate_preview_name(
                st.session_state.naming_scheme,
                st.session_state.separators,
                st.session_state.custom_prefix,
                st.session_state.preview_options
            )
            preview_placeholder.success(f"**Preview:** `{preview_name}`")
            preview_caption_placeholder.caption("_This is a sample preview. Each campaign will use its own actual data._")
            preview_divider_placeholder.divider()

    st.divider()

    # ASIN Short Names Section
    st.header("ASIN Short Names (Optional)")
    st.write("Download a template file with all unique ASINs from your bulk file, add short names, and upload it back to replace ASINs in campaign/ad group names.")

    asin_col1, asin_col2 = st.columns(2)

    with asin_col1:
        st.subheader("Step 1: Download Template")
        if st.session_state.unique_asins:
            template_file = create_asin_template(st.session_state.unique_asins)

            st.download_button(
                label=f"📥 Download ASIN Template ({len(st.session_state.unique_asins)} ASINs)",
                data=template_file,
                file_name="ASIN_Short_Names_Template.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )
            st.caption("⚠️ Fill in the 'Short_Name' column (max 50 characters) and upload below")
        else:
            st.warning("No ASINs found in the processed data")

    with asin_col2:
        st.subheader("Step 2: Upload Completed Template")
        uploaded_shortname_file = st.file_uploader("Upload ASIN Short Names File", type=['xlsx'], key="asin_shortname_upload")

        if uploaded_shortname_file:
            try:
                uploaded_df = pd.read_excel(uploaded_shortname_file, sheet_name='ASIN_Short_Names')

                # Validate the file
                is_valid, validation_errors, asin_map = validate_asin_shortname_file(
                    uploaded_df,
                    st.session_state.unique_asins
                )

                if is_valid:
                    st.success(f"✓ Valid! Found {len(asin_map)} ASIN short names")
                    st.session_state.asin_short_names = asin_map

                    # Checkbox to enable mapping
                    st.session_state.use_short_names = st.checkbox(
                        "✅ Map Short Names to ASINs",
                        value=st.session_state.use_short_names,
                        help="Replace ASINs in campaign and ad group names with 'ASIN-ShortName'"
                    )

                    if st.session_state.use_short_names:
                        st.info("🔄 ASINs will be replaced with 'ASIN-ShortName' format")
                else:
                    st.error("❌ Validation Failed:")
                    for error in validation_errors:
                        st.error(f"• {error}")
                    st.session_state.use_short_names = False

            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
                st.session_state.use_short_names = False

    st.divider()

    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back to Upload"):
            st.session_state.step = 1
            st.rerun()
    with col_next:
        if st.session_state.naming_scheme:
            if st.button("Continue to Preview →", type="primary"):
                st.session_state.step = 3
                st.rerun()

# STEP 3: Preview
elif st.session_state.step == 3:
    st.header("Step 3: Preview Changes")
    
    campaigns = st.session_state.processed_data
    campaign_list = list(campaigns.values())
    
    # Search
    search_col1, search_col2 = st.columns([3, 1])
    with search_col1:
        campaign_id_search = st.text_input("Search by Campaign ID:")
    with search_col2:
        if st.button("🔍 Search") and campaign_id_search:
            for idx, campaign in enumerate(campaign_list):
                if campaign['id'] == campaign_id_search:
                    st.session_state.current_page = (idx // 10) + 1
                    st.rerun()
    
    # Generate deduplicated campaign names for all campaigns
    campaign_names_list = []
    for campaign in campaign_list:
        new_campaign_name = generate_campaign_name(
            campaign,
            st.session_state.naming_scheme,
            st.session_state.separators,
            st.session_state.custom_prefix,
            st.session_state.asin_short_names,
            st.session_state.use_short_names
        )
        campaign_names_list.append((campaign['id'], new_campaign_name))

    deduplicated_campaign_names = deduplicate_names(campaign_names_list)

    # Pagination
    items_per_page = 10
    total_pages = (len(campaign_list) + items_per_page - 1) // items_per_page
    start_idx = (st.session_state.current_page - 1) * items_per_page
    end_idx = min(start_idx + items_per_page, len(campaign_list))
    current_campaigns = campaign_list[start_idx:end_idx]

    # Display campaigns
    for campaign in current_campaigns:
        final_campaign_name = deduplicated_campaign_names[campaign['id']]

        with st.expander(f"Campaign {campaign['id']} ({len(campaign['ad_groups'])} ad groups)"):
            st.write("**Old Name:**")
            st.code(campaign['name'], language=None)
            st.write("**New Name:**")
            st.code(final_campaign_name, language=None)

            if st.checkbox("View Ad Groups", key=f"view_ag_{campaign['id']}"):
                # Generate deduplicated ad group names for this campaign
                adgroup_names_list = []
                for ad_group in campaign['ad_groups'].values():
                    new_adgroup_name = generate_adgroup_name(
                        ad_group,
                        st.session_state.asin_short_names,
                        st.session_state.use_short_names
                    )
                    adgroup_names_list.append((ad_group['id'], new_adgroup_name))

                deduplicated_adgroup_names = deduplicate_names(adgroup_names_list)

                for ad_group in campaign['ad_groups'].values():
                    final_adgroup_name = deduplicated_adgroup_names[ad_group['id']]
                    st.write(f"**Ad Group:** {ad_group['id']}")
                    st.write(f"Old: `{ad_group['name']}`")
                    st.write(f"New: `{final_adgroup_name}`")
                    st.divider()
    
    # Pagination controls
    page_col1, page_col2, page_col3 = st.columns([1, 2, 1])
    with page_col1:
        if st.button("← Previous", disabled=(st.session_state.current_page == 1)):
            st.session_state.current_page -= 1
            st.rerun()
    with page_col2:
        st.write(f"Page {st.session_state.current_page} of {total_pages} ({len(campaign_list)} campaigns)")
    with page_col3:
        if st.button("Next →", disabled=(st.session_state.current_page == total_pages)):
            st.session_state.current_page += 1
            st.rerun()
    
    # Error log
    if st.session_state.errors:
        with st.expander(f"⚠️ Warnings & Errors ({len(st.session_state.errors)})"):
            for error in st.session_state.errors:
                st.warning(error)
            
            error_text = '\n'.join(st.session_state.errors)
            st.download_button(
                "📥 Download Error Log",
                data=error_text,
                file_name="error_log.txt",
                mime="text/plain"
            )
    
    st.divider()
    
    col_back, col_next = st.columns(2)
    with col_back:
        if st.button("← Back to Naming Scheme"):
            st.session_state.step = 2
            st.rerun()
    with col_next:
        if st.button("Continue to Export →", type="primary"):
            st.session_state.step = 4
            st.rerun()

# STEP 4: Export
elif st.session_state.step == 4:
    st.header("Step 4: Export Bulk Update File")
    
    campaigns = st.session_state.processed_data
    total_campaigns = len(campaigns)
    total_ad_groups = sum(len(c['ad_groups']) for c in campaigns.values())
    
    st.success(f"✓ Ready to export {total_campaigns} campaigns and {total_ad_groups} ad groups")
    
    st.write("**Summary:**")
    st.write(f"- Total Campaigns: **{total_campaigns}**")
    st.write(f"- Total Ad Groups: **{total_ad_groups}**")
    st.write("- Ready to upload to Amazon Ads")
    
    # Create bulk file
    bulk_df = create_bulk_file(
        campaigns,
        st.session_state.naming_scheme,
        st.session_state.separators,
        st.session_state.custom_prefix,
        st.session_state.asin_short_names,
        st.session_state.use_short_names
    )
    
    # Convert to Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        bulk_df.to_excel(writer, index=False, header=False, sheet_name='Sponsored Products')
    output.seek(0)
    
    # Download buttons in columns
    download_col1, download_col2 = st.columns(2)

    with download_col1:
        st.download_button(
            label="📥 Download Bulk Update File",
            data=output,
            file_name="amazon_ads_bulk_update.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True
        )

    with download_col2:
        # Generate nomenclature document
        nomenclature_doc = generate_nomenclature_document(
            st.session_state.naming_scheme,
            st.session_state.separators,
            st.session_state.custom_prefix,
            campaigns
        )

        st.download_button(
            label="📄 Download Nomenclature Guide",
            data=nomenclature_doc,
            file_name="naming_scheme_guide.txt",
            mime="text/plain",
            use_container_width=True
        )

    st.info("💡 **Tip:** Download both files! The Nomenclature Guide explains your naming scheme in detail.")

    # Preview file contents
    with st.expander("👁️ Preview Bulk File Contents (First 20 rows)"):
        st.dataframe(bulk_df.head(20), use_container_width=True)

    # Preview nomenclature document
    with st.expander("📖 Preview Nomenclature Guide"):
        st.text(nomenclature_doc)
    
    st.divider()
    
    col_back, col_restart = st.columns(2)
    with col_back:
        if st.button("← Back to Preview"):
            st.session_state.step = 3
            st.rerun()
    with col_restart:
        if st.button("🔄 Start Over"):
            # Reset all session state
            st.session_state.step = 1
            st.session_state.processed_data = None
            st.session_state.naming_scheme = []
            st.session_state.separators = {}
            st.session_state.custom_prefix = 'SP'
            st.session_state.errors = []
            st.session_state.current_page = 1
            st.session_state.sp_sheet_data = None
            st.session_state.global_asin_performance = {}
            st.session_state.unique_asins = []
            st.session_state.asin_short_names = {}
            st.session_state.use_short_names = False
            st.session_state.preview_options = {
                'targetingType': 'M',
                'matchTypes': ['Ex', 'Br'],
                'biddingStrategy': 'Fix',
                'bestPlacement': 'TOS',
                'adGroupCount': 3
            }
            st.rerun()
