ganglia report:

copy dynamictorque_report.json and torque_report.json to ganglia web: /opt/www/cxperf/ganglia/graph.d/

copy default.json from /opt/www/cxperf/ganglia/conf to /var/lib/ganglia-web/conf/default.json
and add new reports to it:

{
	"included_reports": ["dynamictorque_report","torque_report","load_report","mem_report","cpu_report","network_report"]
}

then they will appear on the host view