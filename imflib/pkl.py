# Based on SMPTE 429-8-2007: https://ieeexplore.ieee.org/document/7290849
# With additions from SMPTE 2067-2-2020: https://ieeexplore.ieee.org/document/9097478

import dataclasses, typing, datetime, uuid
import xml.etree.ElementTree as et
from imflib import xsd_datetime_to_datetime, xsd_optional_usertext, xsd_optional_security
from imflib import UserText, Security

@dataclasses.dataclass(frozen=True)
class Asset:
    """An asset packed into this IMF package"""

    hash:str
    """Base64-encoded message digest of the asset"""
    
    size:int
    """File size of the asset in bytes"""

    type:str
    """MIME-type of the asset"""

    hash_algorithm:str="http://www.w3.org/2000/09/xmldsig#sha1" # NOTE: Addition via SMPTE 2067-2
    """Name of the digest type used by the hash"""

    id:uuid.UUID=dataclasses.field(default_factory=uuid.uuid4)
    """Unique asset identifier encoded as a urn:UUID [RFC 4122]"""

    original_file_name:typing.Optional[UserText]=None
    """Optional original file name of the asset when the PKL was created"""

    annotation_text:typing.Optional[UserText]=None
    """Optional description of the asset"""

    @classmethod
    def from_xml(cls, xml:et.Element, ns:typing.Dict) -> "Asset":
        """Create an asset from an XML element"""

        id = uuid.UUID(xml.find("Id", ns).text)
        size = int(xml.find("Size", ns).text)
        type = xml.find("Type", ns).text
        
        # As of 2067-2-2020, http://www.w3.org/2000/09/xmldsig#sha1 is the only supported algorithm
        hash = xml.find("Hash", ns).text
        hash_algorithm = xml.find("HashAlgorithm", ns).attrib.get("Algorithm").split("#")[-1]
        
        original_file_name = xsd_optional_usertext(xml.find("OriginalFileName", ns))
        annotation_text = xsd_optional_usertext(xml.find("AnnotationText", ns))
        
        return cls(
            id=id,
            hash=hash,
            hash_algorithm=hash_algorithm,
            size=size,
            type=type,
            original_file_name=original_file_name,
            annotation_text=annotation_text
        )
    
    def __post_init__(self):
        """Validate additional constraints"""

        # Size is an xs:PositiveInteger
        if not self.size > 0: raise ValueError("Size must be a positive integer.")

        # TODO: Add mime-type guessing via `mimetypes` module? Or maybe nah.


@dataclasses.dataclass(frozen=True)
class Pkl:
    """An IMF PKL Packing List"""

    issuer:UserText
    """The person or company that issued this PKL"""

    creator:UserText
    """The facility or system that created this PKL"""
    
    issue_date:datetime.datetime=dataclasses.field(default_factory=datetime.datetime.now)
    """Datetime this PKL was issued"""

    assets:typing.List["Asset"]=dataclasses.field(default_factory=list)
    """The list of `Asset` s contained in this package"""

    id:uuid.UUID=dataclasses.field(default_factory=uuid.uuid4)
    """Unique package identifier encoded as a urn:UUID [RFC 4122]"""

    annotation_text:typing.Optional[UserText]=None
    """Optional description of the distribution package"""

    group_id:typing.Optional[uuid.UUID]=None
    """Optional UUID referencing a group of multiple packages to which this package belongs"""

    icon_id:typing.Optional[uuid.UUID]=None
    """Optional UUID reference to an image asset to be used as an icon"""

    # TODO: Implement signing
    # NOTE: Signature and Signer must both be present; maybe make this one thing

    security:typing.Optional[Security]=None
    """Optional digital signer and signature authenticating the PKL"""


    @classmethod
    def from_file(cls, path:str) -> "Pkl":
        """Parse an existing PKL from a given file path"""

        file_pkl = et.parse(path)
        return cls.from_xml(file_pkl.getroot(), {"":"http://www.smpte-ra.org/schemas/2067-2/2016/PKL"})
    
    @classmethod
    def from_xml(cls, xml:et.Element, ns:typing.Optional[dict]=None)->"Pkl":
        """Parse a PKL from XML"""

        print(xml.tag)

        id = uuid.UUID(xml.find("Id", ns).text)
        issuer = UserText.from_xml(xml.find("Issuer", ns))
        creator = UserText.from_xml(xml.find("Creator", ns))
        issue_date = xsd_datetime_to_datetime(xml.find("IssueDate",ns).text)

        # TODO: Iterator...?
        assets = [Asset.from_xml(asset,ns) for asset in xml.findall("AssetList/Asset",ns)]

        annotation_text = xsd_optional_usertext(xml.find("AnnotationText", ns))
        group_id = uuid.UUID(xml.find("GroupId", ns)) if xml.find("GroupId", ns) is not None else None
        icon_id = uuid.UUID(xml.find("IconId", ns)) if xml.find("IconId", ns) is not None else None

        security = xsd_optional_security(
            xml_signer=xml.find("Signer",ns),
            xml_signature=xml.find("ds:Signature",{"ds":"http://www.w3.org/2000/09/xmldsig#"})
        )

        return cls(
            id=id,
            issuer=issuer,
            creator=creator,
            issue_date=issue_date,
            assets=assets,
            annotation_text=annotation_text,
            group_id=group_id,
            icon_id=icon_id,
            security=security
        )
    
    def get_asset(self, id:str) -> "Asset":
        """Get an Asset from the PKL based on the URN ID"""
        for asset in self.assets:
            if asset.id == id: return asset        
        return None
    
    @property
    def total_size(self)->int:
        """Total size of assets in bytes"""
        return sum(a.size for a in self.assets)
