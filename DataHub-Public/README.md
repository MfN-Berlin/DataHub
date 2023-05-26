DataHub: A Comprehensive Data Integration System for the Collection Data and Digitization Projects in the Natural History Museum, Berlin.

Author:  majid.vafadar@mfn.berlin 

MfN DataHub (Museum fuer Naturkunde Berlin Data Hub) is a central integration system to automate digitization data pipelines from various digitization stations to their target systems. DataHub has been developed in the Museum of Natural History Berlin to support the integration of digitization and collection projects to the scientific data management systems. An open-source web service together with Apache Airflow as a workflow engine would handle the entire data pipelines automatically. 

A central integration system benefits various collections that are seeking a better and faster unified solution, while keeping up with the speed of digitization to reduce backlogs. The museums with heterogeneous collections of specimens in particular might use several collection management systems across disciplines. Consequently, it becomes increasingly harder to integrate the outcome of the collection and digitization projects to the internal and external databases in one go. The digitization processes in which images, text and metadata have been produced in different collections with different structure and format are mostly large and multi-dimensional, hence they should be processed efficiently. Processed data has to be stored in a safe storage system to integrate further to the inventory databases, collection management systems, archives and media and data portals. The digital specimens associated with the collected data would be accessible and updated for the collection, digitization, researchers and also the public. Data can be enriched using external online databases (e.g. Taxonomy Backbones) or further integrate into them as the new input.

DataHub addresses the increasing need for a faster integration of datasets to avoid waiting time in manual processes.  All required steps are automated using Python algorithms and libraries. The data integration process in DataHub is scalable from integrating simple Excel sheets to mass digitization outputs with large datasets. A common interface of museum wide identifiers ensures the automated data flow in multiple projects has been unified by an established template, following the requirements of multiple collection and digitization projects; using common data standards. Once the structure for a new project is established and added to DataHub, the automated data pipeline starts to transform and transfer the datasets to their targets, with predefined automated code. The open-source code is accessible on Githaub.

MfN DataHub integrates the outcome of mass digitization projects, e.g. Entomology collections by Picturae, Mollusca collections by DORA, archive and text datasets by Kitodo, and digitization on demand by the researchers. DataHub is also fully integrated with ODK collect, an offline mobile data collection app to accommodate data entry for assessments, inventory, field data collection and photography. DataHub interfaces are compliant with the modular collection management system of the museum called DINA (https://dina-project.net), which communicates based on OpenAPI specification to be fully integrated.


**HOW TO DEPLOY:**

Local:

Build the docker image:
`docker-compose build`

Test the image:
`docker-compose up -d`

Regenerate Open API Schema:
./manage.py generateschema --file openapi-schema.yml

