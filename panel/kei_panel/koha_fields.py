"""Plain names of the destinations the field mapping screen offers outside
the bibliographic MARC fields (marc21.py): Koha's patron (borrowers)
fields, grouped as the patron form groups them, and the MARC 21 authority
fields. English here; the screen translates them."""

from __future__ import annotations

# (group, [(field, name)]): the order of the Function list in patron mode.
PATRON_GROUPS = [
    ("Identification", [
        ("cardnumber", "Card number"), ("surname", "Surname (or full name)"), ("firstname", "First name"),
        ("preferred_name", "Preferred name"), ("middle_name", "Middle name"), ("title", "Salutation"),
        ("othernames", "Other name"), ("initials", "Initials"), ("pronouns", "Pronouns"),
        ("dateofbirth", "Date of birth"), ("sex", "Gender"), ("userid", "Username (login)"),
        ("patron_attributes", "Patron attributes (CPF, RG...)"),
    ]),
    ("Main address", [
        ("streetnumber", "Street number"), ("streettype", "Street type"), ("address", "Address"),
        ("address2", "Address 2 (district)"), ("city", "City"), ("state", "State (UF)"),
        ("zipcode", "ZIP code (CEP)"), ("country", "Country"),
    ]),
    ("Contact", [
        ("email", "Email"), ("phone", "Phone"), ("mobile", "Mobile phone"), ("fax", "Fax"),
        ("emailpro", "Secondary email"), ("phonepro", "Secondary phone"), ("smsalertnumber", "SMS number"),
        ("primary_contact_method", "Main contact method"), ("lang", "Language of notices"),
    ]),
    ("Alternate address", [
        ("B_streetnumber", "Alternate: street number"), ("B_streettype", "Alternate: street type"),
        ("B_address", "Alternate: address"), ("B_address2", "Alternate: address 2"),
        ("B_city", "Alternate: city"), ("B_state", "Alternate: state"), ("B_zipcode", "Alternate: ZIP code"),
        ("B_country", "Alternate: country"), ("B_email", "Alternate: email"), ("B_phone", "Alternate: phone"),
    ]),
    ("Library and category", [
        ("branchcode", "Library"), ("categorycode", "Patron category"), ("dateenrolled", "Registration date"),
        ("dateexpiry", "Expiry date"), ("date_renewed", "Date renewed"),
        ("password_expiration_date", "Password expiry date"), ("sort1", "Sort 1 (course, class...)"),
        ("sort2", "Sort 2"),
    ]),
    ("Alternate contact", [
        ("contactname", "Contact: surname"), ("contactfirstname", "Contact: first name"),
        ("contacttitle", "Contact: salutation"), ("relationship", "Relationship"),
        ("guarantor_id", "Guarantor"), ("guarantor_relationship", "Guarantor relationship"),
        ("altcontactsurname", "Alternate contact: surname"),
        ("altcontactfirstname", "Alternate contact: first name"),
        ("altcontactaddress1", "Alternate contact: address"), ("altcontactaddress2", "Alternate contact: address 2"),
        ("altcontactaddress3", "Alternate contact: city"), ("altcontactstate", "Alternate contact: state"),
        ("altcontactzipcode", "Alternate contact: ZIP code"), ("altcontactcountry", "Alternate contact: country"),
        ("altcontactphone", "Alternate contact: phone"),
    ]),
    ("Notes and flags", [
        ("borrowernotes", "Circulation note"), ("opacnote", "OPAC note"), ("contactnote", "Contact note"),
        ("debarred", "Restricted until"), ("debarredcomment", "Restriction comment"),
        ("gonenoaddress", "Gone, no address"), ("lost", "Card lost"), ("privacy", "Privacy"),
        ("privacy_guarantor_fines", "Guarantor sees fines"),
        ("privacy_guarantor_checkouts", "Guarantor sees checkouts"),
        ("checkprevcheckout", "Check previous checkouts"), ("autorenew_checkouts", "Auto-renew checkouts"),
        ("sms_provider_id", "SMS provider"),
    ]),
    ("Sensitive", [
        ("password", "Password"), ("secret", "Two-factor secret"), ("auth_method", "Login method"),
        ("flags", "Staff permissions"), ("overdrive_auth_token", "OverDrive token"), ("protected", "Protected"),
        ("anonymized", "Anonymized"), ("login_attempts", "Login attempts"), ("updated_on", "Updated on"),
        ("lastseen", "Last seen"),
    ]),
]
PATRON_LABELS = {field: name for _, fields in PATRON_GROUPS for field, name in fields}
PATRON_GROUP = {field: group for group, fields in PATRON_GROUPS for field, _ in fields}

AUTHORITY_LABELS = {
    "001": "Control number", "003": "Control number identifier", "005": "Date and time of latest transaction",
    "008": "Fixed-length data elements", "010$a": "LC control number", "024$a": "Other identifier",
    "100$a": "Heading: personal name", "100$d": "Heading: dates", "110$a": "Heading: corporate name",
    "111$a": "Heading: meeting name", "130$a": "Heading: uniform title", "150$a": "Heading: topical term",
    "151$a": "Heading: geographic name", "155$a": "Heading: genre/form", "180$x": "Heading: subdivision",
    "400$a": "See from: personal name", "410$a": "See from: corporate name", "411$a": "See from: meeting name",
    "430$a": "See from: uniform title", "450$a": "See from: topical term", "451$a": "See from: geographic name",
    "455$a": "See from: genre/form", "480$x": "See from: subdivision", "500$a": "See also: personal name",
    "510$a": "See also: corporate name", "511$a": "See also: meeting name", "530$a": "See also: uniform title",
    "550$a": "See also: topical term", "551$a": "See also: geographic name", "555$a": "See also: genre/form",
    "580$x": "See also: subdivision", "667$a": "Nonpublic note", "670$a": "Source data found",
    "675$a": "Source data not found", "680$a": "Public note", "700$a": "Linked heading: personal name",
    "710$a": "Linked heading: corporate name", "750$a": "Linked heading: topical term",
    "152$b": "Koha authority type", "942$a": "Koha authority type",
}

# Destinations whose values are codes of the Koha instance: the screen shows
# their "from/to" list and the instance's codes to pick from.
CODE_KINDS = {"952$a": "branches", "952$b": "branches", "branchcode": "branches", "952$y": "itemtypes",
              "942$c": "itemtypes", "952$c": "locations", "categorycode": "categories"}
