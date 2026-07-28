type Props = { params: Promise<{ route?: string[] }> };
export default async function DemoRoute({ params }: Props) {
  const { route = [] } = await params;
  const fragment = route.length ? `/${route.join('/')}` : '/login';
  return <main className="demo-frame"><iframe title="Hiring Agent Demo" src={`/demo-template?v=20260727-run-delete#${fragment}`} /></main>;
}
