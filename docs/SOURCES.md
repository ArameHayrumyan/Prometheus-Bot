# Source Registry

All **199** seeded acquisition sources (163 student-tier, 36 youth-tier), extracted from the seed migrations (`alembic/versions/0002…0010`).

> ⚠️ **The live registry is the database**, not this file — admins extend it at runtime with `/addsource` (and tune per-source behavior with `/sourcemeta`, `/togglesource`). Regenerate this document after new seed migrations. Inspect the live state anytime with `/listsources`.

## Student tier

### RSS feeds (polled every 20 min) — 9

| Source | Category | Country | Notes |
|---|---|---|---|
| [Mladiinfo](https://www.mladiinfo.eu/feed/) | aggregator | — |  |
| [Opportunity Desk](https://opportunitydesk.org/feed/) | aggregator | — |  |
| [ProFellow Blog](https://www.profellow.com/feed/) | aggregator | — |  |
| [Scholars4Dev](https://www.scholars4dev.com/feed/) | aggregator | — |  |
| [Scholarship Positions](https://scholarship-positions.com/feed/) | aggregator | — |  |
| [Euraxess - jobs & fellowships](https://euraxess.ec.europa.eu/f/rss/jobs) | fellowship | EU |  |
| [RemoteOK - dev jobs](https://remoteok.com/remote-dev-jobs.rss) | startup_board | — |  |
| [WeWorkRemotely - all jobs](https://weworkremotely.com/remote-jobs.rss) | startup_board | — |  |
| [WeWorkRemotely - programming](https://weworkremotely.com/categories/remote-programming-jobs.rss) | startup_board | — |  |

### Newsletter mailbox (IMAP, every 15 min) — 1

| Source | Category | Country | Notes |
|---|---|---|---|
| [Newsletter mailbox (IMAP)](imap://inbox) | newsletter | — |  |

### Community boards (every 4 h) — 4

| Source | Category | Country | Notes |
|---|---|---|---|
| [HN Who is Hiring (Algolia)](https://hn.algolia.com/api/v1/search_by_date?query=%22who%20is%20hiring%22&tags=story&hitsPerPage=3) | community | — | hn |
| [r/bioinformatics](https://www.reddit.com/r/bioinformatics/new.json?limit=40) | community | — |  |
| [r/datascience](https://www.reddit.com/r/datascience/new.json?limit=40) | community | — |  |
| [r/MachineLearning](https://www.reddit.com/r/MachineLearning/new.json?limit=40) | community | — |  |

### LinkedIn guest search (every 6 h, throttled) — 4

| Source | Category | Country | Notes |
|---|---|---|---|
| [LinkedIn guest - bioinformatics (remote)](https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=bioinformatics&location=Worldwide&f_WT=2&start=0) | linkedin | — |  |
| [LinkedIn guest - DS intern jobs worldwide (SEO page)](https://www.linkedin.com/jobs/data-science-intern-jobs-worldwide) | linkedin | — |  |
| [LinkedIn guest - DS internships (worldwide remote)](https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=data%20science%20intern&location=Worldwide&f_WT=2&start=0) | linkedin | — |  |
| [LinkedIn guest - junior software (Armenia)](https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=junior%20software%20engineer&location=Armenia&start=0) | linkedin | Armenia |  |

### Web pages (every 4 h; Playwright for JS-heavy) — 145

| Source | Category | Country | Notes |
|---|---|---|---|
| [AcademicJobsOnline](https://academicjobsonline.org/ajo/jobs?joblist-0-0-0-0-0-d) | academic_board | — |  |
| [Nature Careers - bioinformatics](https://www.nature.com/naturecareers/jobs/bioinformatics) | academic_board | — |  |
| [Nature Careers - life science internships EU](https://www.nature.com/naturecareers/jobs/life-science/internship/europe/full-time/) | academic_board | EU |  |
| [Armacad (Armenia-focused academia)](https://armacad.info/) | aggregator | Armenia |  |
| [Bachelorsportal - DS & Big Data scholarships](https://www.bachelorsportal.com/search/scholarships/bachelor/data-science-big-data) | aggregator | — |  |
| [Mastersportal - scholarships finder](https://www.mastersportal.com/scholarships/) | aggregator | — |  |
| [Opportunities Circle](https://www.opportunitiescircle.com/) | aggregator | — |  |
| [Opportunities For Youth](https://opportunitiesforyouth.org/) | aggregator | — |  |
| [PhDportal - DS & Big Data scholarships](https://www.phdportal.com/search/scholarships/phd/data-science-big-data) | aggregator | — |  |
| [ScholarshipsAds - internship scholarships](https://www.scholarshipsads.com/category/degree/internship) | aggregator | — |  |
| [WeMakeScholars](https://www.wemakescholars.com/scholarship) | aggregator | — |  |
| [Youth Opportunities](https://www.youthop.com/) | aggregator | — |  |
| [Bioinformatics.ca job postings](https://bioinformatics.ca/job-postings/) | bioinfo_board | Canada |  |
| [Bioinformatics.org jobs](https://www.bioinformatics.org/jobs/) | bioinfo_board | — |  |
| [Biotecnika - KWIK scholarship](https://www.biotecnika.org/2023/11/kwik-scholarship-for-biotech-life-science-ug-pg-students/) | bioinfo_board | India |  |
| [HackBio - bioinformatics/DS internships](https://internship.thehackbio.com/opportunities-in-bfx) | bioinfo_board | — |  |
| [ISCB Careers (computational biology)](https://careers.iscb.org/) | bioinfo_board | — |  |
| [Neuromatch (comp-neuro courses & community)](https://neuromatch.io/) | bioinfo_board | — |  |
| [PathwaysToScience - bioinformatics](https://www.pathwaystoscience.org/discipline.aspx?sort=TEC-Bioinformatics_Bioinformatics) | bioinfo_board | USA |  |
| [PathwaysToScience - bioinformatics & genomics](https://www.pathwaystoscience.org/Discipline.aspx?sort=TEC-Bioinformatics_Bioinformatics+%2A+Genomics) | bioinfo_board | USA |  |
| [EPAM Careers Armenia](https://www.epam.com/careers/job-listings?country=Armenia) | company | Armenia |  |
| [JetBrains Careers](https://www.jetbrains.com/careers/jobs/) | company | — |  |
| [Krisp Careers](https://krisp.ai/careers/) | company | Armenia |  |
| [NVIDIA University Jobs](https://www.nvidia.com/en-us/about-nvidia/careers/university-recruiting/) | company | — |  |
| [Picsart Careers](https://picsart.com/jobs) | company | Armenia |  |
| [ServiceTitan Careers (Armenia)](https://www.servicetitan.com/careers) | company | Armenia |  |
| [Synopsys Armenia careers](https://careers.synopsys.com/search-jobs/Armenia) | company | Armenia |  |
| [EMBO fellowships & grants](https://www.embo.org/funding/fellowships-grants-and-career-support/) | fellowship | EU |  |
| [Australia Awards](https://www.dfat.gov.au/people-to-people/australia-awards/australia-awards-scholarships) | gov_scholarship | Australia |  |
| [Chevening Scholarships](https://www.chevening.org/scholarships/) | gov_scholarship | UK |  |
| [Commonwealth Scholarships](https://cscuk.fcdo.gov.uk/scholarships/) | gov_scholarship | UK |  |
| [DAAD RISE research internships](https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/?detail=50015638) | gov_scholarship | Germany | classic RISE restricted to NA/UK/IE students; hard gate handles eligibility per listing |
| [DAAD Scholarship Database](https://www2.daad.de/deutschland/stipendium/datenbank/en/21148-scholarship-database/) | gov_scholarship | Germany |  |
| [Erasmus+ Opportunities](https://erasmus-plus.ec.europa.eu/opportunities/opportunities-for-individuals) | gov_scholarship | EU |  |
| [Fulbright Armenia](https://am.usembassy.gov/education-culture/educational-exchange/) | gov_scholarship | USA |  |
| [Japan MEXT Scholarship](https://www.studyinjapan.go.jp/en/planning/scholarship/) | gov_scholarship | Japan |  |
| [Open Society Foundations Grants](https://www.opensocietyfoundations.org/grants) | gov_scholarship | — |  |
| [Swiss Government Excellence Scholarships](https://www.sbfi.admin.ch/sbfi/en/home/education/scholarships-and-grants/swiss-government-excellence-scholarships.html) | gov_scholarship | Switzerland |  |
| [Vanier Canada Graduate Scholarships](https://vanier.gc.ca/en/home-accueil.html) | gov_scholarship | Canada |  |
| [Devpost - hackathons](https://devpost.com/hackathons) | hackathons | — |  |
| [DrivenData - competitions](https://www.drivendata.org/competitions/) | hackathons | — |  |
| [Kaggle - competitions](https://www.kaggle.com/competitions) | hackathons | — |  |
| [Microsoft Imagine Cup](https://imaginecup.microsoft.com/) | hackathons | — |  |
| [MLH - hackathon season](https://mlh.io/seasons/2027/events) | hackathons | — |  |
| [NASA Space Apps Challenge](https://www.spaceappschallenge.org/) | hackathons | — |  |
| [Zindi - competitions](https://zindi.africa/competitions) | hackathons | — |  |
| [Achilleus - medical informatics internship](https://eic-achilleus.eu/job/it-specialist-for-medical-informatics/) | institute | EU |  |
| [Broad Institute Careers](https://broadinstitute.avature.net/en_US/careers/SearchJobs) | institute | USA |  |
| [CERN Students & Graduates](https://careers.cern/students-graduates) | institute | Switzerland |  |
| [EMBL Internships](https://www.embl.org/careers/internships/) | institute | EU |  |
| [EMBL Jobs](https://www.embl.org/jobs/searchjobs/) | institute | EU |  |
| [EMBL TechDev Internship Programme](https://www.embl.org/about/info/scientific-visitor-programme/fellowships/techdev/) | institute | EU |  |
| [EPFL Open Positions](https://www.epfl.ch/about/working/working-at-epfl/job-openings/) | institute | Switzerland |  |
| [ESA student internships](https://www.esa.int/About_Us/Careers_at_ESA/Student_internships) | institute | EU |  |
| [ETH Zurich Open Positions](https://jobs.ethz.ch/) | institute | Switzerland |  |
| [ISTA - internships & scholarships](https://ista.ac.at/en/education/internship-and-scholarship/) | institute | Austria |  |
| [Max Planck Society Jobs](https://www.mpg.de/jobboard) | institute | Germany |  |
| [MPI CBS - Neural Data Science internships](https://www.cbs.mpg.de/career/internships) | institute | Germany |  |
| [MPI for Intelligent Systems - internships](https://is.mpg.de/en/internships) | institute | Germany |  |
| [MPIIB-ISI Integrative Science Internship](https://www.mpiib-berlin.mpg.de/2155069/mpiib-isi-application-guide) | institute | Germany |  |
| [RIGI Research Internship (MPI-IS)](https://rig-internships.de/program) | institute | Germany |  |
| [Theory@EMBL Visitor Programme](https://www.embl.org/about/info/scientific-visitor-programme/) | institute | EU |  |
| [UN ICC - data science internships](https://www.unicc.org/working-with-icc/data-science-intern/) | institute | — |  |
| [Wellcome Sanger Institute Jobs](https://jobs.sanger.ac.uk/vacancies.html) | institute | UK |  |
| [aijobs.net - AI/ML job board](https://aijobs.net/) | internship | — | seeded instead of a single Deep Origin posting; title filter catches intern/junior roles |
| [Allen Institute for AI - internships](https://allenai.org/internships) | internship | USA |  |
| [ANQ.am job board (Armenia)](https://anq.am/en/jobs) | internship | Armenia | seeded instead of a single NVIDIA-Yerevan posting UUID |
| [RBC Borealis - ML research internships](https://rbcborealis.com/internships/) | internship | Canada | GPA screened |
| [Staff.am - data science internships](https://staff.am/jobs/data-science/data-science-internship) | internship | Armenia |  |
| [Vector Institute - AI research internships](https://vectorinstitute.ai/research-talent/students/ai-research-internships/) | internship | Canada |  |
| [IES Internships - CS/Data/Math](https://www.iesabroad.org/intern-abroad/fields/computer-science-math-statistics) | internship_platform | — |  |
| [Intern Abroad HQ - CS & IT](https://www.internhq.com/fields/computer-science-and-it/) | internship_platform | — |  |
| [Prosple - DS internships (USA/remote)](https://prosple.com/data-science-internships-in-usa) | internship_platform | USA |  |
| [Indeed - DS student internships](https://www.indeed.com/q-data-science-student-internship-jobs.html) | job_board | USA | Cloudflare-protected; may fail without SCRAPER_PROXY_URL - handler logs and skips |
| [A*STAR GIS computational biology internships (via jglab)](https://jglab.org/2021/07/01/research-internships-in-singapore-2019-2020/) | lab | Singapore | GPA screened; stale blog directory (2019-2020) — links may be outdated; verify per listing |
| [Armenian Bioinformatics Institute - open positions](https://oldsite.abi.am/about-us/open-positions/) | lab | Armenia |  |
| [HSE CS faculty - internships](https://cs.hse.ru/en/internships/) | lab | Russia | GPA screened |
| [YerevaNN - ML research lab](https://yerevann.com/about/) | lab | Armenia | student research projects |
| [FindAMasters - scholarships](https://www.findamasters.com/masters-degrees/computer-science/) | masters_board | — |  |
| [Augustana tech-majors internship hub](https://careers.augustana.edu/resources/internships-jobs-for-tech-majors-computer-science-data-it/) | meta_source | USA |  |
| [Code.org - CS internships & apprenticeships](https://code.org/en-US/students/internships-and-apprenticeships) | meta_source | USA |  |
| [Global Internship List (GitHub)](https://github.com/VikashPR/Global-Internship-List) | meta_source | — |  |
| [MPI-IS internship guide (Zhijing Jin, GitHub)](https://github.com/zhijing-jin/nlp-phd-global-equality/blob/main/mpi_internship.md) | meta_source | — |  |
| [Bioconductor](https://bioconductor.org/) | opensource | — |  |
| [Biopython GSoC](https://biopython.org/wiki/Google_Summer_of_Code) | opensource | — |  |
| [cBioPortal GSoC](https://github.com/cBioPortal/GSoC) | opensource | — |  |
| [EleutherAI Community](https://www.eleuther.ai/community) | opensource | — |  |
| [EleutherAI SOAR (Summer of Open AI Research)](https://www.eleuther.ai/soar) | opensource | — |  |
| [EMBL-EBI Google Summer of Code](https://www.ebi.ac.uk/about/events/events/public-event/2025/2026-google-summer-of-code/) | opensource | EU |  |
| [Galaxy Project](https://galaxyproject.org/) | opensource | — |  |
| [GMOD / Open Genome Informatics GSoC](https://gmod.org/wiki/GSoC.html) | opensource | — |  |
| [Google Summer of Code - get started](https://summerofcode.withgoogle.com/get-started) | opensource | — | SPA; Playwright locally, httpx fallback on free host |
| [Igalia Coding Experience](https://www.igalia.com/coding-experience/) | opensource | — |  |
| [LAION](https://laion.ai/) | opensource | — |  |
| [LFX Mentorship (Linux Foundation)](https://mentorship.lfx.linuxfoundation.org/) | opensource | — |  |
| [Liquid Galaxy Project (GSoC org)](https://summerofcode.withgoogle.com/programs/2026/organizations/liquid-galaxy-project) | opensource | — |  |
| [MLH Fellowship](https://fellowship.mlh.io/) | opensource | — |  |
| [Open Bioinformatics Foundation GSoC](https://www.open-bio.org/events/gsoc/) | opensource | — |  |
| [OpenMined / PySyft](https://openmined.org/pysyft/) | opensource | — |  |
| [OpenMined PySyft (GitHub)](https://github.com/OpenMined/PySyft) | opensource | — |  |
| [OSGeo Google Summer of Code](https://wiki.osgeo.org/wiki/Google_Summer_of_Code_2025) | opensource | — |  |
| [Outreachy Applicant Guide](https://www.outreachy.org/docs/applicant/) | opensource | — | paid remote internships explicitly for underrepresented backgrounds; no GPA screen |
| [Summer of Bitcoin](https://www.summerofbitcoin.org/) | opensource | — |  |
| [FindAPhD - bioinformatics](https://www.findaphd.com/phds/bioinformatics/?01M0) | phd_board | — |  |
| [FindAPhD - funded CS/DS](https://www.findaphd.com/phds/computer-science/?01M0) | phd_board | — |  |
| [Make it in Germany](https://www.make-it-in-germany.com/en/working-in-germany/job-listings) | relocation | Germany |  |
| [Work in Denmark - IT](https://www.workindenmark.dk/search-job?q=software) | relocation | Denmark |  |
| [Work in Estonia](https://workinestonia.com/jobs/) | relocation | Estonia |  |
| [ABI - Vine bioinformatics internship (Binder Lab)](https://www.abi.am/careers/vine-bioinformatics-internship-binder-lab-2025) | research | Armenia | GPA screened |
| [INSAIT SURF - summer undergraduate research fellowship](https://insait.ai/surf/) | research | Bulgaria | GPA screened; GPA 3.5; fully funded incl. travel |
| [Iowa IHG - summer bioinformatics internship](https://humangenetics.medicine.uiowa.edu/education-division/summer-internship-bioinformatics) | research | USA | GPA screened |
| [Nanjing University - summer research intern program](https://stuex.nju.edu.cn/en_/57248/list.htm) | research | China | GPA screened |
| [Ramapo College - bioinformatics research opportunities](https://bioinformatics.ramapo.edu/research/index.html) | research | USA | directory |
| [UC Davis - global research opportunities](https://globallearning.ucdavis.edu/pathways/experience/internships/global-research) | research | — | GPA screened; directory |
| [UChicago CCRF - international research opportunities](https://ccrf.uchicago.edu/international-research-opportunities) | research | — | GPA screened; directory |
| [UCSD bioinformatics - nationwide research opportunities](https://bioinformatics.ucsd.edu/undergrad/nationwide-opportunities) | research | USA | GPA screened; directory |
| [Cohere For AI Scholars Program (blog)](https://cohere.com/blog/c4ai-scholars-program) | research_program | — |  |
| [Cohere Labs Open Science Community](https://cohere.com/research/open-science) | research_program | — |  |
| [Cohere Labs Scholars Program](https://cohere.com/research/scholars-program) | research_program | — |  |
| [Hugging Face AI Research Residency](https://huggingface.co/blog/ai-residency) | research_program | — |  |
| [Wellfound (AngelList) - internships](https://wellfound.com/role/r/software-engineer-intern) | startup_board | — |  |
| [AWS Educate](https://aws.amazon.com/education/awseducate/) | student_program | — |  |
| [Cisco Networking Academy](https://www.netacad.com/) | student_program | — |  |
| [GitHub Education for students](https://github.com/education/students) | student_program | — |  |
| [Amgen Scholars](https://amgenscholars.com/) | summer_research | — |  |
| [Caltech SURF](https://sfp.caltech.edu/undergraduate-research/programs/surf) | summer_research | USA |  |
| [DESY Summer Student Programme](https://summerstudents.desy.de/) | summer_research | Germany |  |
| [ETH Zurich - Student Summer Research Fellowship](https://inf.ethz.ch/studies/summer-research-fellowship.html) | summer_research | Switzerland |  |
| [KAUST VSRP](https://vsrp.kaust.edu.sa/) | summer_research | Saudi Arabia |  |
| [Mitacs Globalink Research Internship](https://www.mitacs.ca/our-programs/globalink-research-internship-students/) | summer_research | Canada |  |
| [OIST Research Internships](https://www.oist.jp/research/research-internships) | summer_research | Japan |  |
| [RIKEN student programs](https://www.riken.jp/en/careers/programs/) | summer_research | Japan |  |
| [Summer@EPFL](https://www.epfl.ch/schools/ic/education/summer-at-epfl/) | summer_research | Switzerland |  |
| [UTokyo UTRIP](https://www.s.u-tokyo.ac.jp/en/UTRIP/) | summer_research | Japan |  |
| [SASTRA COMBIGS - bioinformatics internship](https://sastra.edu/combigs/intern.html) | training | India |  |
| [Vienna BioCenter summer school](https://training.vbc.ac.at/summer-school/) | training | Austria | GPA screened |
| [42 Yerevan](https://42yerevan.am/) | university | Armenia |  |
| [Armenian Code Academy](https://aca.am/) | university | Armenia |  |
| [AUA Career Opportunities](https://careers.aua.am/) | university | Armenia |  |
| [Enterprise Incubator Foundation News](https://www.eif.am/eng/news/) | university | Armenia |  |
| [FAST Foundation (fellowships & programs)](https://fast.foundation/) | university | Armenia |  |
| [HKU CS - research internship programme](https://www.cs.hku.hk/rintern/) | university | Hong Kong |  |
| [TUMO Labs](https://tumolabs.am/en/) | university | Armenia |  |
| [ULB - MA-BINF bioinformatics internships](https://sciences.ulb.be/en/computer-sciences/internships/m-binf-internships) | university | Belgium |  |
| [URI - CS & DS projects/internships](https://web.uri.edu/cs/academics/projects-and-internships/) | university | USA |  |

## Youth tier (🌱 relaxed gate, routes to the youth queue)

All webpage sources — 36 total.

| Source | Category | Country | Notes |
|---|---|---|---|
| [ARMACAD - Armenia](https://armacad.info/country/armenia) | aggregator | Armenia |  |
| [Scholarships.plus](https://scholarships.plus/) | aggregator | Armenia |  |
| [Scholarships.plus - Armenia](https://scholarships.plus/scholarships/all-degrees/armenia/) | aggregator | Armenia |  |
| [Harry Messel International Science School (Sydney)](https://www.sydney.edu.au/science/iss) | camp | Australia | age 16-19; free; verify URL — submitted short path may redirect |
| [MIT admissions - STEM summer programs list](https://mitadmissions.org/apply/prepare/summer/) | camp | USA | directory; age 15-18; scholarship-track |
| [ANCA - Armenian American scholarship guide](https://anca.org/armenian-american-scholarship-guide/) | directory | Armenia |  |
| [Armenian Assembly - financial aid directory](https://www.armenian-assembly.org/post/armenian-assembly-releases-updated-financial-aid-directory) | directory | Armenia |  |
| [Birthright Armenia - internship organizations](https://www.birthrightarmenia.org/en/program/internshipOrganizations/20) | directory | Armenia |  |
| [EU4Armenia - 20 free youth opportunities](https://eu4armenia.eu/dont-miss-out-20-free-opportunities-for-young-people-in-armenia/) | directory | Armenia |  |
| [Armath engineering laboratories (UATE)](https://armath.am/en/about) | ecosystem | Armenia | age 10-18; free; 600+ free after-school engineering labs |
| [AGBU Programs](https://agbu.org/programs) | official_program_page | Armenia |  |
| [AGBU Scholarship Eligibility](https://agbu.org/scholarship-eligibility) | official_program_page | Armenia |  |
| [AGBU Scholarships](https://agbu.org/scholarships) | official_program_page | Armenia |  |
| [ANCA Youth](https://anca.org/youth/) | official_program_page | Armenia |  |
| [ARISC - grants & fellowships](https://arisc.org/?cat=59) | official_program_page | Armenia |  |
| [Armenian Assembly - Intern DC](https://www.armenian-assembly.org/students/interndc) | official_program_page | Armenia |  |
| [Armenian Assembly - internships](https://www.armenian-assembly.org/internship) | official_program_page | Armenia |  |
| [COAF - alumni programs](https://www.coaf.org/programs/education/coaf-alumni-programs) | official_program_page | Armenia |  |
| [COAF - Youredjian scholarships](https://www.coaf.org/blog/youredjian-scholarships-2025) | official_program_page | Armenia |  |
| [CALICO informatics competition (UC Berkeley)](https://calico.cs.berkeley.edu) | olympiad | USA | age 14-19; free |
| [CodeHER competition](https://codehercompetition.org) | olympiad | — | age 13-19; free; girls/non-binary students |
| [CPI - student programming contests hub](https://joincpi.org/contests) | olympiad | — | directory; age 13-19; free |
| [FIRST Global Challenge (robotics)](https://first.global/fgc/) | olympiad | — | age 14-18; scholarship-track |
| [International Computer Science Competition](https://icscompetition.org) | olympiad | — | age 13-19; unknown |
| [International Computing Olympiad](https://www.computingolympiad.org/) | olympiad | — | age 13-19; unknown |
| [International Mathematical Olympiad (IMO)](https://www.imo-official.org/) | olympiad | — | age 14-19; free |
| [International Olympiad in Informatics (IOI)](https://ioinformatics.org/) | olympiad | — | age 14-19; free |
| [Newark Academy CTF](https://ctf.nactf.net) | olympiad | — | age 13-19; free; prizes US-only, participation worldwide |
| [Olymp.am - Armenian national subject olympiads](https://www.olymp.am) | olympiad | Armenia | age grades 6-12; free |
| [Open Olympiad in Informatics (Moscow)](https://inf-open.ru/?lang=en) | olympiad | Russia | age 13-19; fully-funded |
| [picoCTF (CMU cybersecurity)](https://picoctf.org) | olympiad | — | age 13-19; free; competition + year-round practice, certificates |
| [TeamsCode - programming contests](https://www.teamscode.org/contests/) | olympiad | — | age 13-19; free |
| [World Robot Olympiad (global)](https://wro-association.org/) | olympiad | — | age 8-19; scholarship-track; substituted for the submitted India national page |
| [Lumiere Research Inclusion Foundation](https://lumiere.foundation) | research | — | age 15-19; fully-funded; free 1-on-1 research mentorship for low-income students worldwide |
| [MIT high-school research programs (RSI & PRIMES)](https://math.mit.edu/research/highschool/) | research | USA | directory; age 15-18; scholarship-track |
| [Research Science Institute (RSI, MIT)](https://math.mit.edu/research/highschool/rsi/) | research | USA | age grade 11; fully-funded |
